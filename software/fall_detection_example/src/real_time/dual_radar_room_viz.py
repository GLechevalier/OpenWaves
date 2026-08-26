"""
Dual-radar room-level point cloud visualization.

Both radars transform their local point clouds into a shared room frame,
so all detected points appear in the same 3D space.

Usage:
    1. Set RADAR*_CLI_PORT constants below.
    2. Set RADAR1_POSE and RADAR2_POSE (position in metres, angles in degrees).
    3. python src/real_time/dual_radar_room_viz.py

Radar local frame (TI IWR convention):
    +X  forward (range direction, away from radar face)
    +Y  left
    +Z  up

Room frame:
    user-defined — set RADAR*_POSE so that +X / +Y / +Z match your layout.
    Example: +X = east wall, +Y = north wall, +Z = ceiling.

Rotation convention (intrinsic ZYX):
    yaw   — spin around room Z (up); 0° means radar faces room +X
    pitch — tilt up/down (positive = nose up)
    roll  — lean left/right (usually 0 for a wall/ceiling mount)
"""

import os
import sys
import time
import threading
from dataclasses import dataclass

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

sys.path.append(os.getcwd())

from src.real_time.radar_utils.RadarParser import RadarParser
from src.helpers.doppler_to_color import doppler_to_color
from src.data_processors.posture_detector import PostureDetector


# -- COM PORT CONFIG ------------------------------------------------------------
RADAR1_CLI_PORT  = "COM11"
RADAR1_DATA_PORT = "COM14"   # unused for SingleCOMPort devices
RADAR2_CLI_PORT  = "COM15"
RADAR2_DATA_PORT = "COM8"    # unused for SingleCOMPort devices

CFG_PATH   = "cfg/Tracking_MidBw.cfg"
N          = 10     # sliding-window depth (frames kept per radar)
MAX_FRAMES = 500
# ------------------------------------------------------------------------------


# -- RADAR POSES IN ROOM -------------------------------------------------------
@dataclass
class RadarPose:
    """Position (metres) and orientation (degrees) of a radar in the room frame."""
    x:     float = 0.0   # metres
    y:     float = 0.0
    z:     float = 0.0   # height above floor
    yaw:   float = 0.0   # rotation around room Z; 0° = radar faces room +X
    pitch: float = 0.0   # tilt up/down (positive = nose up)
    roll:  float = 0.0   # lean left/right (usually 0)


#   Both radars side by side (0.3 m apart along Y), same height and orientation
RADAR1_POSE = RadarPose(x=0.0, y=0.0,  z=0.8, yaw=0.0, pitch=0.0, roll=0.0)
RADAR2_POSE = RadarPose(x=0.3, y=0.0,  z=0.8, yaw=0.0, pitch=0.0, roll=0.0)
# ------------------------------------------------------------------------------


# -- GEOMETRY HELPERS ----------------------------------------------------------

def _rotation_matrix(yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
    """Intrinsic ZYX rotation matrix: R = Rz(yaw) @ Ry(pitch) @ Rx(roll)."""
    y = np.radians(yaw_deg)
    p = np.radians(pitch_deg)
    r = np.radians(roll_deg)
    Rz = np.array([[np.cos(y), -np.sin(y), 0.0],
                   [np.sin(y),  np.cos(y), 0.0],
                   [0.0,        0.0,       1.0]])
    Ry = np.array([[ np.cos(p), 0.0, np.sin(p)],
                   [ 0.0,       1.0, 0.0       ],
                   [-np.sin(p), 0.0, np.cos(p)]])
    Rx = np.array([[1.0, 0.0,        0.0       ],
                   [0.0, np.cos(r), -np.sin(r) ],
                   [0.0, np.sin(r),  np.cos(r) ]])
    return Rz @ Ry @ Rx


def transform_points(pc: np.ndarray, pose: RadarPose) -> np.ndarray:
    """Rotate and translate a point cloud from radar local frame to room frame.

    pc : (N, 4+) array — columns [x, y, z, doppler, ...]
    Returns a copy with the xyz columns replaced by room-frame coordinates.
    """
    R = _rotation_matrix(pose.yaw, pose.pitch, pose.roll)
    t = np.array([pose.x, pose.y, pose.z])
    out = pc.copy()
    out[:, :3] = pc[:, :3] @ R.T + t
    return out


def _pose_axes_arrows(pose: RadarPose, length: float = 0.3):
    """Return (origins, vectors, colors) for X/Y/Z axes arrows at a radar pose."""
    R = _rotation_matrix(pose.yaw, pose.pitch, pose.roll)
    origin = np.array([pose.x, pose.y, pose.z])
    origins = np.tile(origin, (3, 1))
    vectors = (R * length).T          # columns of R scaled -> rows = X, Y, Z axes
    colors  = [[220, 50,  50,  255],  # X red
               [50,  200, 50,  255],  # Y green
               [50,  100, 220, 255]]  # Z blue
    return origins, vectors, colors
# ------------------------------------------------------------------------------


class RadarParserExplicit(RadarParser):
    """RadarParser that opens specific COM ports instead of auto-detecting."""

    def __init__(self, cli_port: str, data_port: str):
        self._cli_port  = cli_port
        self._data_port = data_port
        super().__init__()

    def detect_and_open_COM_ports(self):
        import serial
        import time as _t
        # Wait up to 15 s for the port to appear (it may be re-enumerating after a reset)
        deadline = _t.time() + 15
        while True:
            try:
                self.cliCom = serial.Serial(self._cli_port, 115200, timeout=1)
                break
            except serial.SerialException:
                if _t.time() > deadline:
                    raise
                print(f"  [{self._cli_port}] not ready, retrying...")
                _t.sleep(1)

        self.cliCom.write(b"version\r\n")
        _t.sleep(0.1)
        self.cliCom.readline(1024)          # echo
        ack = self.cliCom.readline(1024)

        if b'L684x' in ack:
            self.parserType = "DoubleCOMPort6844"
            self.dataCom = serial.Serial(self._data_port, 1250000, timeout=1)
        elif b'WR18' in ack or b'WR16' in ack or b'WR14' in ack:
            self.parserType = "DoubleCOMPort6844"
            self.dataCom = serial.Serial(self._data_port, 921600, timeout=1)
        else:
            self.parserType = "SingleCOMPort"
            self.dataCom = self.cliCom      # data streams on CLI port after baud change

        data_label = (self._data_port if self.parserType != "SingleCOMPort"
                      else f"{self._cli_port} (=CLI)")
        print(f"Opened: CLI={self._cli_port}  Data={data_label}  type={self.parserType}")
        return self.parserType, self.cliCom, self.dataCom


class PrefixedPostureDetector(PostureDetector):
    """PostureDetector that logs to a per-radar sub-namespace inside the room view.

    The bounding box is emitted in room frame by transforming f['pts'] with pose.
    """

    def __init__(self, prefix: str, pose: RadarPose, **kwargs):
        super().__init__(**kwargs)
        self._prefix = prefix
        self._pose   = pose
        self._R      = _rotation_matrix(pose.yaw, pose.pitch, pose.roll)
        self._t      = np.array([pose.x, pose.y, pose.z])

    def _log(self, label: str, f: dict) -> str:
        p = self._prefix
        color = self._COLORS[label]
        rr.log(f"{p}/posture/label",  rr.Scalars(self._LABEL_TO_INT[label]))
        rr.log(f"{p}/posture/status", rr.TextLog(
            f"POSTURE -> {label.upper()}", level=rr.TextLogLevel.INFO))
        if f:
            rr.log(f"{p}/posture/features/z_mean",    rr.Scalars(f["z_mean"]))
            rr.log(f"{p}/posture/features/z_extent",  rr.Scalars(f["z_extent"]))
            rr.log(f"{p}/posture/features/xy_spread", rr.Scalars(f["xy_spread"]))
            rr.log(f"{p}/posture/features/flatness",  rr.Scalars(f["flatness"]))
            pts_room = f["pts"] @ self._R.T + self._t   # f["pts"] is (N,3) local
            mins, maxs = pts_room.min(axis=0), pts_room.max(axis=0)
            rr.log(f"{p}/posture_bbox", rr.Boxes3D(
                centers=[(mins + maxs) / 2],
                half_sizes=[(maxs - mins) / 2],
                colors=[(*color[:3], 80)],
            ))
        return label


def make_microdoppler_logger(prefix: str):
    """Returns a stateful microdoppler logger bound to a per-radar prefix."""
    waterfall = [None]
    HISTORY = 128

    def _log(outputDict, frame_idx):
        udoppler    = outputDict.get('microDopplerOutput')
        num_targets = outputDict.get('numTargets', 0)
        if udoppler is None or num_targets == 0:
            return
        num_bins    = udoppler.shape[1]
        spectrum    = np.mean(udoppler.astype(np.float32), axis=0)
        spectrum_db = 20.0 * np.log10(np.maximum(spectrum, 1e-6))
        if waterfall[0] is None:
            waterfall[0] = np.full((num_bins, HISTORY), spectrum_db.min(), dtype=np.float32)
        waterfall[0] = np.roll(waterfall[0], shift=-1, axis=1)
        waterfall[0][:, -1] = spectrum_db
        rr.log(f"{prefix}/microdoppler/spectrogram",
               rr.Tensor(np.flipud(waterfall[0]), dim_names=["doppler_freq", "time"]))

    return _log


def run_scan_loop(radar_parser, pose: RadarPose,
                  start_idx: int, max_frames: int,
                  point_cloud_list: list, N: int,
                  prefix: str):
    """Scan loop for one radar — runs in its own thread.

    Points are transformed into the room frame before logging.
    prefix should be something like "room/radar1" so all points land
    inside the shared Spatial3DView rooted at "room/".
    """
    frame_idx        = start_idx
    posture_detector = PrefixedPostureDetector(prefix=prefix, pose=pose, radar_height=0.85)
    log_microdoppler = make_microdoppler_logger(prefix)
    print(f"[{prefix}] Thread started.")

    while frame_idx < start_idx + max_frames:
        try:
            outputDict = radar_parser.read_raw_frame_bytes()

            if not outputDict or outputDict.get('error', 0) != 0:
                print(f"[{prefix}] Frame {frame_idx}: error")
                frame_idx += 1
                continue

            rr.set_time("frame", sequence=frame_idx)

            point_cloud_list.insert(0, outputDict["pointCloud"])
            if len(point_cloud_list) > N:
                point_cloud_list.pop()

            numPts = outputDict.get('numDetectedPoints', 0)
            if numPts > 0:
                tot_pts, z_sum = 0, 0.0
                for i, pc_local in enumerate(point_cloud_list):
                    pc_room = transform_points(pc_local, pose)
                    rr.log(f"{prefix}/point_cloud{i+1}", rr.Points3D(
                        positions=pc_room[:, :3],
                        radii=0.03,
                        colors=doppler_to_color(pc_room[:, 3]),
                    ))
                    z_sum   += np.sum(pc_room[:, 2])
                    tot_pts += len(pc_room)
                rr.log(f"{prefix}/mean_height", rr.Scalars(z_sum / tot_pts))
                posture = posture_detector.update(point_cloud_list)   # local frame intentional
                print(f"[{prefix}] Frame {frame_idx}: posture={posture}")
            else:
                print(f"[{prefix}] Frame {frame_idx}: 0 points")

            numTracks = outputDict.get('numDetectedTracks', 0)
            if numTracks > 0:
                tracks_local = outputDict['trackData'][:numTracks]
                # Tracks are [id, x, y, z, ...] in radar local frame
                ids      = tracks_local[:, 0]
                xyz_local = tracks_local[:, 1:4]
                xyz_room  = xyz_local @ _rotation_matrix(pose.yaw, pose.pitch, pose.roll).T \
                            + np.array([pose.x, pose.y, pose.z])
                rr.log(f"{prefix}/tracks", rr.Points3D(
                    positions=xyz_room,
                    radii=0.08,
                    labels=[str(int(tid)) for tid in ids],
                ))

            log_microdoppler(outputDict, frame_idx)
            frame_idx += 1

        except KeyboardInterrupt:
            print(f"\n[{prefix}] Stopped by user.")
            return frame_idx
        except Exception as e:
            print(f"[{prefix}] Frame {frame_idx} exception: {e}")
            frame_idx += 1

    return frame_idx


def cleanup_radar(name: str, parser: RadarParser):
    print(f"\nStopping {name}...")
    try:
        parser.sensor_stop()
        parser.warm_reset_and_wait()
    except Exception as e:
        print(f"  [{name}] cleanup warning: {e}")
    finally:
        if parser.cliCom and getattr(parser.cliCom, 'is_open', False):
            parser.cliCom.close()
        if parser.dataCom and parser.dataCom is not parser.cliCom \
                and getattr(parser.dataCom, 'is_open', False):
            parser.dataCom.close()


# -- MAIN ----------------------------------------------------------------------

rr.init("dual_radar_room_viz")
rr.spawn()
time.sleep(2)

rr.send_blueprint(rrb.Blueprint(
    rrb.Horizontal(
        rrb.Spatial3DView(origin="room", name="Room"),
        rrb.Vertical(
            rrb.TimeSeriesView(origin="room/radar1/mean_height", name="Radar 1 — Height"),
            rrb.TimeSeriesView(origin="room/radar2/mean_height", name="Radar 2 — Height"),
        ),
    )
))

# Log static room geometry: floor grid and radar body + orientation axes
rr.log("room/floor", rr.Boxes3D(
    centers=[[1.5, 0.0, 0.0]],
    half_sizes=[[2.5, 2.5, 0.01]],
    colors=[[60, 60, 60, 80]],
))

for label, pose, color in [
    ("radar1", RADAR1_POSE, [255, 255, 255, 255]),
    ("radar2", RADAR2_POSE, [255, 200, 100, 255]),
]:
    rr.log(f"room/{label}/body", rr.Boxes3D(
        centers=[[pose.x, pose.y, pose.z]],
        half_sizes=[[0.1, 0.05, 0.18]],
        colors=[color],
    ))
    origins, vectors, colors = _pose_axes_arrows(pose)
    rr.log(f"room/{label}/axes", rr.Arrows3D(
        origins=origins, vectors=vectors, colors=colors,
    ))

# Open both ports first, before any config is sent.
# sendConfig changes baud rate and triggers sensorStart, which can briefly
# drop the other radar's USB COM port if they share a hub.
print("Opening radar 1...")
radar1 = RadarParserExplicit(RADAR1_CLI_PORT, RADAR1_DATA_PORT)
print("Opening radar 2...")
radar2 = RadarParserExplicit(RADAR2_CLI_PORT, RADAR2_DATA_PORT)

print("Configuring radar 1...")
radar1.sendConfig(CFG_PATH)
print("Configuring radar 2...")
radar2.sendConfig(CFG_PATH)

pc_list1, pc_list2 = [], []

t1 = threading.Thread(
    target=run_scan_loop,
    kwargs=dict(radar_parser=radar1, pose=RADAR1_POSE,
                start_idx=0, max_frames=MAX_FRAMES,
                point_cloud_list=pc_list1, N=N, prefix="room/radar1"),
    daemon=True, name="radar1",
)
t2 = threading.Thread(
    target=run_scan_loop,
    kwargs=dict(radar_parser=radar2, pose=RADAR2_POSE,
                start_idx=0, max_frames=MAX_FRAMES,
                point_cloud_list=pc_list2, N=N, prefix="room/radar2"),
    daemon=True, name="radar2",
)

print("Starting radar threads...")
t1.start()
t2.start()

try:
    t1.join()
    t2.join()
except KeyboardInterrupt:
    print("\nInterrupted — stopping radars...")

cleanup_radar("radar1", radar1)
cleanup_radar("radar2", radar2)
print("Done.")
