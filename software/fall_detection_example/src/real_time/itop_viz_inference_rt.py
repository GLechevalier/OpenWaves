"""
Real-time SPiKE inference + Rerun visualization on selected ITOP frames.
"""

import os
import sys
import time
import argparse
import numpy as np
import h5py
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
from model import model_builder
from trainer_itop import create_criterion
from datasets.itop import ITOP
from utils.config_utils import load_config, set_random_seed
from utils.metrics import joint_accuracy
from torch.utils.data import Subset, DataLoader

# -- Config -------------------------------------------------------------------
LABELS_PATH     = os.path.join(SPIKE_DIR, "dataset_SPiKE", "test_labels.h5")
DATASET_DIR     = os.path.join(SPIKE_DIR, "dataset_SPiKE", "test")
FRAMES_PER_CLIP = 3
NUM_POINTS      = 1000
FPS             = 10
start           = 1000
nb              = 2000
SELECTED_IDS    = list(range(start, start + nb))
# -----------------------------------------------------------------------------


def load_frame_full(dataset_dir, frame_id):
    return np.load(os.path.join(dataset_dir, f"{frame_id}.npz"))["arr_0"].astype(np.float32)


def compute_centroid(dataset_dir, sample_id, frames_per_clip):
    """Replicate CenterAug: mean over all points across all clip frames."""
    clip_ids   = [max(0, sample_id - (frames_per_clip - 1 - i)) for i in range(frames_per_clip)]
    all_points = np.concatenate([load_frame_full(dataset_dir, fid) for fid in clip_ids], axis=0)
    return all_points.mean(axis=0)  # (3,)


def remap(pts):
    return np.stack([pts[:, 0], pts[:, 1], pts[:, 2]], axis=1)


def log_skeleton(path, joint_xyz, color_override=None):
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


def predict(clip, device, joints, model, criterion, config, sample_id, results, joints_all):
    clip_gpu   = clip.to(device)
    joints_gpu = joints.to(device)

    output   = model(clip_gpu).reshape(joints_gpu.shape)
    loss     = criterion(output, joints_gpu)
    pck, mean_ap = joint_accuracy(output, joints_gpu, config["threshold"])

    frame_id  = sample_id.squeeze().tolist()[1]
    pred_np   = output.squeeze(0).cpu().numpy().reshape(15,3)   # (1, 15, 3)
    results.append({
        "frame_id": frame_id,
        "loss":     loss.item(),
        "mAP":      mean_ap.item(),
        "pck":      pck.cpu().numpy(),
        "pred":     pred_np,
        "target":   joints.squeeze(0).numpy(),
    })
    print(f"[frame {frame_id:>5}]  loss={loss.item():.4f}  mAP={mean_ap.item():.4f}")

    # -- Visualization --
    centroid = compute_centroid(DATASET_DIR, frame_id, FRAMES_PER_CLIP)

    # Point cloud
    points = load_frame_full(DATASET_DIR, frame_id)
    idx    = np.random.choice(len(points), size=min(NUM_POINTS, len(points)), replace=False)
    points = points[idx] - centroid
    pc_xyz = remap(points)

    # GT joints
    gt_raw = joints_all[frame_id].astype(np.float32)
    gt_xyz = remap(gt_raw - centroid)
    gt_xyz.reshape(15,3)

    # Predicted joints (already in centered space)
    pred_xyz = remap(pred_np)
    return gt_xyz, pc_xyz, pred_xyz

def run(args):
    config = load_config(args.config)
    os.environ["CUDA_VISIBLE_DEVICES"] = str(config["device_args"])
    device = torch.device(0)
    set_random_seed(config["seed"])

    print(config["num_points"])

    # --- Dataset ---
    dataset_test = ITOP(
        root=config["dataset_path"],
        frames_per_clip=config["frames_per_clip"],
        num_points=config["num_points"],
        use_valid_only=config["use_valid_only"],
        target_frame=config["target_frame"],
        train=False,
        aug_list=config["PREPROCESS_TEST"],
    )

    selected_indices = [
        i for i, ident in enumerate(dataset_test.valid_identifiers)
        if int(ident.split("_")[1]) in set(SELECTED_IDS)
    ]
    print(f"Found {len(selected_indices)} valid samples out of {nb} requested")

    subset = Subset(dataset_test, indices=selected_indices)
    loader = DataLoader(subset, batch_size=1, shuffle=False, num_workers=0)

    # --- Model ---
    model = model_builder.create_model(config, dataset_test.num_coord_joints)
    model.to(device)
    model.eval()
    checkpoint = torch.load(args.model, map_location="cpu")
    model.load_state_dict(checkpoint["model"], strict=True)
    print(f"Loaded model from {args.model}")

    criterion = create_criterion(config)

    # --- Load GT joints ---
    with h5py.File(LABELS_PATH, "r") as f:
        joints_all = f["real_world_coordinates"][:]

    # --- Init Rerun ---
    rr.init("itop_viz_pred", spawn=True)
    time.sleep(1)
    rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Y_UP, static=True)

    # --- Inference + Viz loop ---
    results   = []
    frame_num = 0

    with torch.no_grad():
        for clip, joints, sample_id in loader:

            gt_xyz, pc_xyz, pred_xyz = predict(
                clip=clip, 
                device=device, 
                joints=joints, 
                model=model, 
                criterion=criterion, 
                config=config, 
                sample_id=sample_id, 
                joints_all=joints_all,
                results=results
            )

            rr.set_time("frame", sequence=frame_num)

            z      = pc_xyz[:, 2]
            colors = plt_plasma((z - z.min()) / (np.ptp(z) + 1e-6))
            rr.log("world/point_cloud", rr.Points3D(positions=pc_xyz, radii=0.01, colors=colors))

            log_skeleton("world/gt_skeleton",   gt_xyz,   color_override=None)
            log_skeleton("world/pred_skeleton", pred_xyz, color_override=[255, 80, 80])

            frame_num += 1
            time.sleep(1.0 / FPS)

    # --- Summary ---
    print("\n-- Summary ------------------------------")
    print(f"Samples:  {len(results)}")
    print(f"Avg loss: {np.mean([r['loss'] for r in results]):.4f}")
    print(f"Avg mAP:  {np.mean([r['mAP']  for r in results]):.4f}")
    print(f"Avg PCK:  {np.mean([r['pck']  for r in results], axis=0)}")
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPiKE real-time inference + viz")
    parser.add_argument("--config", type=str, default="ITOP-SIDE/1")
    parser.add_argument("--model",  type=str,
                        default=os.path.join(SPIKE_DIR, "SPiKE", "experiments", "ITOP-SIDE", "1", "log", "best_model.pth"))
    args = parser.parse_args()
    run(args)