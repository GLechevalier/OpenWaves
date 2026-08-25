import os
import time
import numpy as np
import rerun as rr
import rerun.blueprint as rrb
import sys

sys.path.append(os.getcwd())

from src.real_time.radar_utils.RadarParser import RadarParser
from src.helpers.doppler_to_color import doppler_to_color
from src.helpers.microdoppler import log_microdoppler
from data_processors.height_estimator import HeightEstimator

# ─────────────────────────────────────────────
# RESET HELPERS
# ─────────────────────────────────────────────


def run_scan_loop(radar_parser, 
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
            
            z_arr = np.concatenate(z_list)
            counts, bin_edges = np.histogram(z_arr, bins=50)

            # Use bin centers as labels
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            rr.log("radar_stats/height_distribution", rr.BarChart(counts))
            rr.log("radar_stats/height_distribution", rr.AnyValues(bin_centers=bin_centers.tolist()))

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
            rrb.Spatial2DView(origin="radar/microdoppler/spectrogram"),
            rrb.BarChartView(origin="radar_stats/height_distribution"),
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
N = 1000
max_frame = 100

# ── SCAN 1 ──────────────────────────────────
print("\n=== SCAN 1: StaticConfig ===")
radar_parser.sendConfig(cfg_path="cfg/StaticConfig.cfg")
frame_idx = run_scan_loop(
    radar_parser=radar_parser,
    start_idx=0,
    max_frames=max_frame,
    point_cloud_list=point_cloud_list,
    N=N
)

print("=== WARM RESET ===")
radar_parser.sensor_stop()
radar_parser.warm_reset_and_wait()

# Re-detect exactly like first boot
radar_parser.redetect_ports()

print("=== SCAN 2 ===")
radar_parser.sendConfig(cfg_path="cfg/StaticConfig2.cfg")
frame_idx = run_scan_loop(radar_parser=radar_parser,
                          start_idx=frame_idx,
                          max_frames=max_frame,
                          point_cloud_list=point_cloud_list,
                          N=N)

print("=== WARM RESET ===")
radar_parser.sensor_stop()
radar_parser.warm_reset_and_wait()
radar_parser.redetect_ports()

print("=== SCAN 3 ===")
radar_parser.sendConfig(cfg_path="cfg/StaticConfig3.cfg")
frame_idx = run_scan_loop(radar_parser=radar_parser,
                          start_idx=frame_idx,
                          max_frames=max_frame,
                          point_cloud_list=point_cloud_list,
                          N=N)


all_points = []
for pc in point_cloud_list:
    for elt in pc:
        all_points.append(elt)

all_points = np.array(all_points)
height_est = HeightEstimator()
result_dict = height_est.process(all_points=all_points, verbose=True)

floor_z_est, a,b,c,d_final = result_dict["floor_z_est"], result_dict["a"], result_dict["b"], result_dict["c"], result_dict["d_final"]

height      = abs(d_final)
pitch_deg   = np.degrees(np.arctan2(b, c))
roll_deg    = np.degrees(np.arctan2(a, c))

height_ransac = abs(d_final)
height_iqr    = abs(floor_z_est)

if abs(height_ransac - height_iqr) > 0.15:
    print(f"⚠ RANSAC height {height_ransac:.3f} m diverges from seed {height_iqr:.3f} m — using seed fallback")
    height = height_iqr
    # optionally refit plane normal using PCA on the z-slice directly (S1 or S2)
else:
    height = height_ransac

print("\n── Results ──────────────────────────────")
print(f"Sensor height : {height:.4f} m")
print(f"Pitch         : {pitch_deg:.2f} °")
print(f"Roll          : {roll_deg:.2f} °")
print("\nPaste into config:")
print(f"sensorPosition 0 0 {height:.3f} {pitch_deg:.2f} {roll_deg:.2f}")

# ── CLEANUP ─────────────────────────────────
print("\nClosing COM ports...")
radar_parser.sensor_stop()  
radar_parser.warm_reset_and_wait()

if radar_parser.cliCom and radar_parser.cliCom != "Don't Care":
    radar_parser.cliCom.close()
if radar_parser.dataCom:
    radar_parser.dataCom.close()