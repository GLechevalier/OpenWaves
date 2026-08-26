import os
import sys
import time
import numpy as np
import h5py
import rerun as rr

SPIKE_DIR = os.environ.get("SPIKE_DIR")
if not SPIKE_DIR:
    sys.exit("Set the SPIKE_DIR environment variable to your SPiKE workspace "
             "(see 'Pose estimation (SPiKE)' in the fall detection README).")
sys.path.append(SPIKE_DIR)
from SPiKE.const.skeleton_joints import joint_connections, joint_indices
from helpers.plt_plasma import plt_plasma

# ── Config ──────────────────────────────────────────────────────────────────
DATASET_DIR       = os.path.join(SPIKE_DIR, "dataset_SPiKE", "test")
LABELS_PATH       = os.path.join(SPIKE_DIR, "dataset_SPiKE", "test_labels.h5")
PRED_PATH         = os.path.join(SPIKE_DIR, "predicted.npy")
FRAME_SELECT_PATH = os.path.join(SPIKE_DIR, "frame_ids.npy")
FRAMES_PER_CLIP   = 3       # must match config
NUM_POINTS        = 500
FPS               = 10
# ────────────────────────────────────────────────────────────────────────────

def load_frame_full(dataset_dir, frame_id):
    """Load full point cloud (no subsampling) for centroid computation."""
    return np.load(os.path.join(dataset_dir, f"{frame_id}.npz"))["arr_0"].astype(np.float32)

def compute_centroid(dataset_dir, sample_id, frames_per_clip):
    """Replicate CenterAug: centroid = mean over all points across all clip frames."""
    clip_ids = [max(0, sample_id - (frames_per_clip - 1 - i)) for i in range(frames_per_clip)]
    all_points = np.concatenate([load_frame_full(dataset_dir, fid) for fid in clip_ids], axis=0)
    return all_points.mean(axis=0)  # (3,)

def remap(pts):
    """Remap (N,3): swap Y and Z so height is vertical."""
    return np.stack([pts[:, 0], pts[:, 1], pts[:, 2]], axis=1)

def log_skeleton(path, joint_xyz, joint_connections, joint_indices, color_override=None):
    """Log joints + limbs to a given rerun path prefix."""
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

# --- Load data ---
with h5py.File(LABELS_PATH, "r") as f:
    joints_all = f["real_world_coordinates"][:]

predictions = np.load(PRED_PATH).reshape(np.load(PRED_PATH).shape[0], 15, 3)
VALID_IDS   = np.load(FRAME_SELECT_PATH).tolist()  # loaded from frame_ids.npy

print(f"Loaded {len(predictions)} predictions for IDs: {VALID_IDS}")
assert len(predictions) == len(VALID_IDS), "Mismatch between predictions and valid IDs"

# --- Init Rerun ---
rr.init("itop_viz_pred", spawn=True)
time.sleep(1)
rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Y_UP, static=True)

# --- Visualize ---
for frame_num, (sample_id, pred_joints) in enumerate(zip(VALID_IDS, predictions)):

    # Compute the same centroid CenterAug used during inference
    centroid = compute_centroid(DATASET_DIR, sample_id, FRAMES_PER_CLIP)

    # Point cloud — subsample then center
    points = load_frame_full(DATASET_DIR, sample_id)
    idx    = np.random.choice(len(points), size=min(NUM_POINTS, len(points)), replace=False)
    points = points[idx] - centroid   # apply centering
    pc_xyz = np.stack([points[:, 0], points[:, 1], points[:, 2]], axis=1)

    # GT joints — apply same centering then remap
    gt_raw = joints_all[sample_id].astype(np.float32)
    gt_xyz = remap(gt_raw - centroid)

    # Predicted joints — already in centered space, just remap
    pred_xyz = remap(pred_joints)

    rr.set_time("frame", sequence=frame_num)

    # Point cloud
    z = pc_xyz[:, 2]
    colors = plt_plasma((z - z.min()) / (np.ptp(z) + 1e-6))
    rr.log("world/point_cloud", rr.Points3D(positions=pc_xyz, radii=0.01, colors=colors))

    # GT skeleton — per-limb colors
    log_skeleton("world/gt_skeleton", gt_xyz, joint_connections, joint_indices,
                 color_override=None)

    # Predicted skeleton — red
    log_skeleton("world/pred_skeleton", pred_xyz, joint_connections, joint_indices,
                 color_override=[255, 80, 80])

    time.sleep(1.0 / FPS)

print("Done.")