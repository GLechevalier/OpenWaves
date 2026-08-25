import os
import time
import numpy as np
import rerun as rr
import rerun.blueprint as rrb
import sys

sys.path.append(os.getcwd())
sys.path.append(r'C:\ti\radar_toolbox_3_20_00_04\tools\visualizers\Applications_Visualizer\common')
sys.path.append(r'C:\ti\radar_toolbox_3_20_00_04\tools\mmwave_data_recorder\src')

from src.real_time.radar_utils.RadarParser import RadarParser
from src.helpers.doppler_to_color import doppler_to_color
from src.helpers.microdoppler import log_microdoppler
from data_processors.posture_detector import PostureDetector

detector = PostureDetector(radar_height=0.85)

def run_scan_loop(radar_parser, 
                  posture_detector,
                  start_idx, max_frames, 
                  point_cloud_list, N=1000):
    """
    Generic scan loop — reusable for both config sets.
    Returns the final frame_idx.
    """
    frame_idx = start_idx
    end_idx = start_idx + max_frames


    while frame_idx < end_idx:
        try:
            outputDict = radar_parser.read_raw_frame_bytes()

            if not outputDict or outputDict.get('error', 0) != 0:
                print(f"Frame {frame_idx}: error={outputDict.get('error', 'empty')}")
                frame_idx += 1
                continue

            rr.set_time("frame", sequence=frame_idx)

            # --- Point Cloud ---
            point_cloud_list.insert(0, outputDict["pointCloud"])
            if len(point_cloud_list) > N:
                point_cloud_list.pop()

            numPts = outputDict.get('numDetectedPoints', 0)
            if numPts > 0:
                tot_pts = 0
                z_g = 0
                z_list = []
                for i, pc in enumerate(point_cloud_list):
                    z_list.append(pc[:, 2])
                    z_g += np.sum(pc[:, 2])
                    rr.log(f"radar/point_cloud{i+1}", rr.Points3D(
                        positions=pc[:, 0:3],
                        radii=0.03,
                        colors=doppler_to_color(pc[:, 3]),
                    ))
                    tot_pts += len(pc)
                rr.log("radar/mean_height", rr.Scalars(z_g / tot_pts))
            else:
                print(f"Frame {frame_idx}: 0 points")

            if numPts > 0:
                posture_detector.collect_sample(point_cloud_list, label=CURRENT_POSTURE)

            # Restore your normal timeline after
            rr.set_time("frame", sequence=frame_idx)

            # --- Tracks ---
            numTracks = outputDict.get('numDetectedTracks', 0)
            if numTracks > 0:
                tracks = outputDict['trackData'][:numTracks]
                rr.log("radar/tracks", rr.Points3D(
                    positions=tracks[:, 1:4],
                    radii=0.08,
                    labels=[str(int(tid)) for tid in tracks[:, 0]],
                ))
                

            # --- Micro-Doppler ---
            log_microdoppler(outputDict, frame_idx)

            frame_idx += 1

        except KeyboardInterrupt:
            print("\nStopped by user.")
            return frame_idx
        except Exception as e:
            print(f"Frame {frame_idx} exception: {e}")
            frame_idx += 1
            continue

    return frame_idx


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────


# Open COM ports
radar_parser = RadarParser()

# Init Rerun
rr.init("radar_3d_viz")
rr.spawn()
time.sleep(2)

rr.send_blueprint(rrb.Blueprint(
    rrb.Horizontal(
        rrb.Spatial3DView(origin="radar"),
        rrb.Vertical(
            rrb.TimeSeriesView(origin="radar/mean_height"),
            rrb.TimeSeriesView(origin="posture/label"),        # 0=stand,1=sit,2=lie
            rrb.TimeSeriesView(origin="posture/features"),     # tilt, elongation, z_extent
            rrb.TensorView(origin="radar/microdoppler/spectrogram"),
        )
    )
))

# Static radar box
rr.log("radar/box", rr.Boxes3D(
    centers=[[0, 0, 0]],
    half_sizes=[[0.1, 0.05, 0.18]],
    colors=[[255, 255, 255, 255]]
))

point_cloud_list = []
N = 20
max_frame = 500
CURRENT_POSTURE = "standing"   # change manually between runs

# ── SCAN 1 ──────────────────────────────────
print("\n=== SCAN 1: StaticConfig ===")
radar_parser.sendConfig(cfg_path="cfg/Tracking_MidBw.cfg")
frame_idx = run_scan_loop(
    radar_parser=radar_parser,
    posture_detector= detector,
    start_idx=0,
    max_frames=max_frame,
    point_cloud_list=point_cloud_list,
    N=N
)
radar_parser.sensor_stop()
radar_parser.warm_reset_and_wait()
radar_parser.redetect_ports()

CURRENT_POSTURE = "sitting"   # change manually between runs
radar_parser.sendConfig(cfg_path="cfg/Tracking_MidBw.cfg")
frame_idx = run_scan_loop(
    radar_parser=radar_parser,
    posture_detector= detector,
    start_idx=0,
    max_frames=max_frame,
    point_cloud_list=point_cloud_list,
    N=N
)

detector.train_and_save("models/posture_svm.pkl")


# ── CLEANUP ─────────────────────────────────
print("\nClosing COM ports...")
radar_parser.sensor_stop()  
radar_parser.warm_reset_and_wait()

if radar_parser.cliCom and radar_parser.cliCom != "Don't Care":
    radar_parser.cliCom.close()
if radar_parser.dataCom:
    radar_parser.dataCom.close()