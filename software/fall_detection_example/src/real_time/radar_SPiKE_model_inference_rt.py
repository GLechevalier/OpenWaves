"""
Real-time SPiKE inference on live radar data + Rerun visualization.

Temporal hierarchy  (both windows slide by 1 at every new raw radar frame)
------------------
  RAW_FRAMES_PER_TRUE_FRAME = 10   raw frames  ->  1 true frame  (sliding)
  FRAMES_PER_CLIP           = 3    true frames ->  1 SPiKE clip  (sliding)

  First inference fires at raw frame index 12
    true-frame 1 : raw[ 0.. 9]
    true-frame 2 : raw[ 1..10]
    true-frame 3 : raw[ 2..11]
  Then every subsequent raw frame produces a new inference.
"""

import os
import sys
import time
import argparse
from collections import deque

import numpy as np
import torch
import rerun as rr

SPIKE_DIR = os.environ.get("SPIKE_DIR")
if not SPIKE_DIR:
    sys.exit("Set the SPIKE_DIR environment variable to your SPiKE workspace "
             "(see 'Pose estimation (SPiKE)' in the fall detection README).")
sys.path.append(os.getcwd())
sys.path.append(SPIKE_DIR)
sys.path.append(os.path.join(SPIKE_DIR, "SPiKE"))

from SPiKE.const.skeleton_joints import joint_connections, joint_indices
from src.helpers.plt_plasma import plt_plasma
from src.helpers.doppler_to_color import doppler_to_color
from src.real_time.radar_utils.RadarParser import RadarParser
from model import model_builder
from datasets.itop import ITOP
from utils.config_utils import load_config, set_random_seed

# -- Config --------------------------------------------------------------------
RAW_FRAMES_PER_TRUE_FRAME = 10   # sliding window width -> one true frame
FRAMES_PER_CLIP           = 3    # sliding window width -> one SPiKE clip
NUM_POINTS                = 1024 # points sampled per true frame for the model
FPS                       = 30   # max Rerun timeline pace
# -----------------------------------------------------------------------------


# -- Helpers -------------------------------------------------------------------

def aggregate(raw_window: deque) -> np.ndarray:
    """
    Concatenate all raw frames in the sliding window into one true-frame PC.
    raw_window : deque of (P_i, ≥3) float32 arrays
    returns    : (ΣP_i, ≥3) float32  — may be empty (0 rows)
                                        if every frame had 0 points
    """
    valid = [f for f in raw_window if len(f) > 0]
    if not valid:
        return np.zeros((0, 3), dtype=np.float32)
    return np.concatenate(valid, axis=0).astype(np.float32)


def sample_and_center(pts: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Sample n points (xyz) from pts and centre them.
    Returns (sampled_centred (n,3), centroid (3,)).
    """
    xyz = pts[:, :3].astype(np.float32)
    if len(xyz) == 0:
        return np.zeros((n, 3), dtype=np.float32), np.zeros(3, dtype=np.float32)
    idx      = np.random.choice(len(xyz), size=n, replace=(len(xyz) < n))
    sampled  = xyz[idx]
    centroid = sampled.mean(axis=0)
    return sampled - centroid, centroid


def build_clip(true_frame_window: deque,
               num_points: int) -> tuple[torch.Tensor, np.ndarray]:
    """
    Stack the FRAMES_PER_CLIP true frames currently in the window into a
    model-ready tensor.  The window is already guaranteed to be full when
    this is called.

    Returns
    -------
    clip     : float32 tensor (1, T, N, 3)
    centroid : (3,)  centroid of the most-recent true frame
    """
    frames   = []
    centroid = np.zeros(3, dtype=np.float32)
    for i, true_frame in enumerate(true_frame_window):   # oldest -> newest
        sampled, c = sample_and_center(true_frame, num_points)
        frames.append(sampled)
        if i == len(true_frame_window) - 1:
            centroid = c
    clip = np.stack(frames, axis=0)                      # (T, N, 3)
    return torch.from_numpy(clip).unsqueeze(0), centroid  # (1, T, N, 3)


def log_skeleton(path: str, joint_xyz: np.ndarray, color_override=None):
    rr.log(f"{path}/joints", rr.Points3D(
        positions=joint_xyz,
        radii=0.03,
        labels=list(joint_indices.values()),
        colors=[color_override or [255, 255, 255]] * 15,
    ))
    for i1, i2, color in joint_connections:
        rgb = color_override or [int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)]
        rr.log(f"{path}/limb_{i1}_{i2}", rr.LineStrips3D(
            strips=[[joint_xyz[i1], joint_xyz[i2]]],
            colors=[rgb],
            radii=0.008,
        ))


# -- Main ----------------------------------------------------------------------

def run(args):
    # -- Config & model -------------------------------------------------------
    config = load_config(args.config)
    os.environ["CUDA_VISIBLE_DEVICES"] = str(config["device_args"])
    device = torch.device(0)
    set_random_seed(config["seed"])

    frames_per_clip = config.get("frames_per_clip", FRAMES_PER_CLIP)
    num_points      = config.get("num_points",      NUM_POINTS)

    # Instantiated only to expose num_coord_joints to model_builder
    dataset_test = ITOP(
        root=config["dataset_path"],
        frames_per_clip=frames_per_clip,
        num_points=num_points,
        use_valid_only=config["use_valid_only"],
        target_frame=config["target_frame"],
        train=False,
        aug_list=config["PREPROCESS_TEST"],
    )

    model = model_builder.create_model(config, dataset_test.num_coord_joints)
    model.to(device).eval()
    checkpoint = torch.load(args.model, map_location="cpu")
    model.load_state_dict(checkpoint["model"], strict=True)

    print(f"Loaded model              : {args.model}")
    print(f"Raw frames / true frame   : {RAW_FRAMES_PER_TRUE_FRAME}  (sliding window)")
    print(f"True frames / clip        : {frames_per_clip}  (sliding window)")
    print(f"Points sampled / true frame: {num_points}")
    print(f"First inference at raw frame index: "
          f"{RAW_FRAMES_PER_TRUE_FRAME + frames_per_clip - 2}\n")
    #   index 0-based: need window of 10 filled (idx 9) then 2 more for 3 true frames

    # -- Init Rerun -----------------------------------------------------------
    rr.init("spike_realtime", spawn=True)
    time.sleep(1)
    rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Y_UP, static=True)

    # -- Open radar -----------------------------------------------------------
    radar = RadarParser()
    parserType, cliCom, dataCom = radar.parserType, radar.cliCom, radar.dataCom
    radar.sendConfig()
    print("Radar configured — starting inference loop …\n")

    # -- Sliding-window buffers ------------------------------------------------
    #   raw_window       : last RAW_FRAMES_PER_TRUE_FRAME raw frames
    #   true_frame_window: last FRAMES_PER_CLIP true frames
    raw_window        = deque(maxlen=RAW_FRAMES_PER_TRUE_FRAME)
    true_frame_window = deque(maxlen=frames_per_clip)

    raw_frame_idx = 0

    try:
        with torch.no_grad():
            while True:
                t0 = time.perf_counter()

                # -- 1. Read one raw radar frame ------------------------------
                outputDict = radar.read_raw_frame_bytes()

                if not outputDict or outputDict.get("error", 0) != 0:
                    print(f"Raw frame {raw_frame_idx}: bad frame, skipping")
                    raw_frame_idx += 1
                    continue

                pc_raw = outputDict["pointCloud"].astype(np.float32)   # (P, ≥3)

                # -- 2. Push into raw sliding window -> new true frame ---------
                raw_window.append(pc_raw)

                # Log the current raw point cloud every tick (always visible)
                rr.set_time("frame", sequence=raw_frame_idx)
                if len(pc_raw) > 0:
                    colors=doppler_to_color(pc_raw[:, 3])
                    rr.log("world/point_cloud/raw", rr.Points3D(
                        positions=pc_raw[:, :3],
                        radii=0.02,
                        colors=colors,
                    ))

                # -- 3. True frame: only available once raw window is full -----
                if len(raw_window) < RAW_FRAMES_PER_TRUE_FRAME:
                    remaining_raw = RAW_FRAMES_PER_TRUE_FRAME - len(raw_window)
                    remaining_true = frames_per_clip - len(true_frame_window)
                    print(f"  Warming up — need {remaining_raw} more raw frame(s) "
                          f"to close true frame, then {remaining_true} more true frame(s) "
                          f"before first inference")
                    raw_frame_idx += 1
                    continue

                true_frame = aggregate(raw_window)           # sliding, not flushed
                true_frame_window.append(true_frame)

                # Visualize the aggregated true-frame point cloud
                if len(true_frame) > 0:
                    colors=doppler_to_color(pc_raw[:, 3])
                    rr.log("world/point_cloud/true_frame", rr.Points3D(
                        positions=true_frame[:, :3],
                        radii=0.025,
                        colors=colors,
                    ))

                # -- 4. Inference: only once the clip window is full -----------
                if len(true_frame_window) < frames_per_clip:
                    remaining = frames_per_clip - len(true_frame_window)
                    print(f"  Warming up — need {remaining} more true frame(s) "
                          f"before first inference")
                    raw_frame_idx += 1
                    continue

                clip, centroid = build_clip(true_frame_window, num_points)
                pred    = model(clip.to(device))
                pred_np = pred.squeeze(0).cpu().numpy().reshape(15, 3)

                # Back to sensor/world frame
                pred_world = pred_np + centroid
                log_skeleton("world/pred_skeleton", pred_world,
                             color_override=[255, 80, 80])

                print(f"raw={raw_frame_idx:>5}  "
                      f"true_pts={len(true_frame):>6}  "
                      f"pred_root={pred_world[0].round(3)}")

                raw_frame_idx += 1

                # Throttle to FPS cap
                elapsed = time.perf_counter() - t0
                sleep   = max(0.0, 1.0 / FPS - elapsed)
                if sleep:
                    time.sleep(sleep)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        print("Closing COM ports …")
        if cliCom and cliCom != "Don't Care":
            cliCom.close()
        if dataCom:
            dataCom.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPiKE real-time radar inference")
    parser.add_argument("--config", type=str, default="ITOP-SIDE/1")
    parser.add_argument(
        "--model", type=str,
        default=os.path.join(SPIKE_DIR, "SPiKE", "experiments", "ITOP-SIDE", "1", "log", "best_model.pth"),
    )
    args = parser.parse_args()
    run(args)