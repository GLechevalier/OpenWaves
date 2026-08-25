"""
Dual-radar real-time point cloud visualization.

Usage:
    1. Set RADAR1_* and RADAR2_* COM port constants below.
       (Device Manager → Ports: each IWR radar shows two ports —
        lower number = CLI (115200 baud), higher = data (921600 baud))
    2. python src/real_time/dual_radar_viz.py

Each radar streams to its own namespace in Rerun:
    radar1/  — first radar
    radar2/  — second radar
"""

import os
import sys
import time
import threading
import numpy as np
import rerun as rr
import rerun.blueprint as rrb

sys.path.append(os.getcwd())
sys.path.append(r'C:\ti\radar_toolbox_3_20_00_04\tools\visualizers\Applications_Visualizer\common')
sys.path.append(r'C:\ti\radar_toolbox_3_20_00_04\tools\mmwave_data_recorder\src')

from src.real_time.radar_utils.RadarParser import RadarParser
from src.helpers.doppler_to_color import doppler_to_color
from src.data_processors.posture_detector import PostureDetector


# ── COM PORT CONFIG ────────────────────────────────────────────────────────────
RADAR1_CLI_PORT  = "COM11"  # ← first radar CLI port
RADAR1_DATA_PORT = "COM14"  # ← first radar data port (unused for SingleCOMPort)
RADAR2_CLI_PORT  = "COM15"  # ← second radar CLI port
RADAR2_DATA_PORT = "COM8"   # ← second radar data port (unused for SingleCOMPort)

CFG_PATH   = "cfg/Tracking_MidBw.cfg"
N          = 10    # sliding window depth (frames kept in point cloud list)
MAX_FRAMES = 500
# ──────────────────────────────────────────────────────────────────────────────


class RadarParserExplicit(RadarParser):
    """RadarParser that opens specific COM ports instead of auto-detecting."""

    def __init__(self, cli_port: str, data_port: str):
        self._cli_port  = cli_port
        self._data_port = data_port
        super().__init__()

    def detect_and_open_COM_ports(self):
        import serial
        import time as _time
        deadline = _time.time() + 15
        while True:
            try:
                self.cliCom = serial.Serial(self._cli_port, 115200, timeout=1)
                break
            except serial.SerialException:
                if _time.time() > deadline:
                    raise
                print(f"  [{self._cli_port}] not ready, retrying...")
                _time.sleep(1)

        # Mirror get_coms_ports version check to pick parser type and data baud rate
        self.cliCom.write(b"version\r\n")
        _time.sleep(0.1)
        self.cliCom.readline(1024)   # echo
        ack = self.cliCom.readline(1024)

        if b'L684x' in ack:
            self.parserType = "DoubleCOMPort6844"
            self.dataCom = serial.Serial(self._data_port, 1250000, timeout=1)
        elif b'WR18' in ack or b'WR16' in ack or b'WR14' in ack:
            self.parserType = "DoubleCOMPort6844"
            self.dataCom = serial.Serial(self._data_port, 921600, timeout=1)
        else:
            # SingleCOMPort: data streams on the CLI port after baud-rate change
            self.parserType = "SingleCOMPort"
            self.dataCom = self.cliCom

        data_label = self._data_port if self.parserType != "SingleCOMPort" else f"{self._cli_port} (=CLI)"
        print(f"Opened: CLI={self._cli_port}  Data={data_label}  type={self.parserType}")
        return self.parserType, self.cliCom, self.dataCom


class PrefixedPostureDetector(PostureDetector):
    """PostureDetector that logs to a per-radar Rerun prefix."""

    def __init__(self, prefix: str, **kwargs):
        super().__init__(**kwargs)
        self._prefix = prefix

    def _log(self, label: str, f: dict) -> str:
        p = self._prefix
        color = self._COLORS[label]
        rr.log(f"{p}/posture/label",  rr.Scalars(self._LABEL_TO_INT[label]))
        rr.log(f"{p}/posture/status", rr.TextLog(
            f"POSTURE → {label.upper()}", level=rr.TextLogLevel.INFO))
        if f:
            rr.log(f"{p}/posture/features/z_mean",   rr.Scalars(f["z_mean"]))
            rr.log(f"{p}/posture/features/z_extent",  rr.Scalars(f["z_extent"]))
            rr.log(f"{p}/posture/features/xy_spread", rr.Scalars(f["xy_spread"]))
            rr.log(f"{p}/posture/features/flatness",  rr.Scalars(f["flatness"]))
            pts = f["pts"]
            mins, maxs = pts.min(axis=0), pts.max(axis=0)
            rr.log(f"{p}/posture_bbox", rr.Boxes3D(
                centers=[(mins + maxs) / 2],
                half_sizes=[(maxs - mins) / 2],
                colors=[(*color[:3], 80)],
            ))
        return label


def make_microdoppler_logger(prefix: str):
    """Returns a stateful microdoppler logger with its own waterfall buffer."""
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


def run_scan_loop(radar_parser, start_idx: int, max_frames: int,
                  point_cloud_list: list, N: int = 1000, prefix: str = "radar"):
    """Scan loop for one radar — runs in its own thread."""
    frame_idx        = start_idx
    posture_detector = PrefixedPostureDetector(prefix=prefix, radar_height=0.85)
    log_microdoppler = make_microdoppler_logger(prefix)

    print(f"[{prefix}] Thread started, waiting for frames...")
    while frame_idx < start_idx + max_frames:
        try:
            outputDict = radar_parser.read_raw_frame_bytes()

            if not outputDict or outputDict.get('error', 0) != 0:
                print(f"[{prefix}] Frame {frame_idx}: error")
                frame_idx += 1
                continue

            # rr.set_time is thread-local in Rerun — safe to call from two threads
            rr.set_time("frame", sequence=frame_idx)

            point_cloud_list.insert(0, outputDict["pointCloud"])
            if len(point_cloud_list) > N:
                point_cloud_list.pop()

            numPts = outputDict.get('numDetectedPoints', 0)
            if numPts > 0:
                tot_pts, z_g = 0, 0.0
                for i, pc in enumerate(point_cloud_list):
                    z_g += np.sum(pc[:, 2])
                    rr.log(f"{prefix}/point_cloud{i+1}", rr.Points3D(
                        positions=pc[:, 0:3],
                        radii=0.03,
                        colors=doppler_to_color(pc[:, 3]),
                    ))
                    tot_pts += len(pc)
                rr.log(f"{prefix}/mean_height", rr.Scalars(z_g / tot_pts))
                posture = posture_detector.update(point_cloud_list)
                print(f"[{prefix}] Frame {frame_idx}: posture={posture}")
            else:
                print(f"[{prefix}] Frame {frame_idx}: 0 points")

            numTracks = outputDict.get('numDetectedTracks', 0)
            if numTracks > 0:
                tracks = outputDict['trackData'][:numTracks]
                rr.log(f"{prefix}/tracks", rr.Points3D(
                    positions=tracks[:, 1:4],
                    radii=0.08,
                    labels=[str(int(tid)) for tid in tracks[:, 0]],
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
        if parser.dataCom and parser.dataCom is not parser.cliCom and getattr(parser.dataCom, 'is_open', False):
            parser.dataCom.close()


# ── MAIN ──────────────────────────────────────────────────────────────────────

rr.init("dual_radar_viz")
rr.spawn()
time.sleep(2)

rr.send_blueprint(rrb.Blueprint(
    rrb.Horizontal(
        rrb.Vertical(
            rrb.Spatial3DView(origin="radar1", name="Radar 1"),
            rrb.TimeSeriesView(origin="radar1/mean_height", name="Radar 1 — Height"),
        ),
        rrb.Vertical(
            rrb.Spatial3DView(origin="radar2", name="Radar 2"),
            rrb.TimeSeriesView(origin="radar2/mean_height", name="Radar 2 — Height"),
        ),
    )
))

rr.log("radar1/box", rr.Boxes3D(centers=[[0, 0, 0]], half_sizes=[[0.1, 0.05, 0.18]], colors=[[255, 255, 255, 255]]))
rr.log("radar2/box", rr.Boxes3D(centers=[[0, 0, 0]], half_sizes=[[0.1, 0.05, 0.18]], colors=[[255, 200, 100, 255]]))

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
    kwargs=dict(radar_parser=radar1, start_idx=0, max_frames=MAX_FRAMES,
                point_cloud_list=pc_list1, N=N, prefix="radar1"),
    daemon=True, name="radar1",
)
t2 = threading.Thread(
    target=run_scan_loop,
    kwargs=dict(radar_parser=radar2, start_idx=0, max_frames=MAX_FRAMES,
                point_cloud_list=pc_list2, N=N, prefix="radar2"),
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
