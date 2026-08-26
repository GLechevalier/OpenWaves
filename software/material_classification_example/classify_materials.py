"""Quick-try demo: classify materials from the shipped radar recordings.

No radar needed. Loads the three bundled captures (a plastic sheet, a stone
wall and a wood plank scanned with the OpenWaves radar), opens one in the
Rerun viewer, then shows that their electromagnetic fingerprints — Capon 3D
beamforming heatmaps, 10 range x 32 azimuth x 16 elevation — are distinct
enough to classify: a logistic regression trained on half of the frames
labels the other half.

    python classify_materials.py                  # viewer + classification
    python classify_materials.py --view stone_wall
    python classify_materials.py --no-viewer      # terminal output only

The full PyTorch pipeline (98.8% across 9 multilayer wall classes) lives in
ML/ — its trained weights ship in ML/outputs_materials/. Those networks are
calibrated to their own measurement campaign, so to use them on your own
walls, record captures with your radar and retrain (ML/src/).
"""

import argparse
from pathlib import Path

import numpy as np
import rerun as rr

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "rerun_recorded_data"
MATERIALS = ["plastic_sheet", "stone_wall", "wood_plank"]


def load_heatmaps(name: str) -> np.ndarray:
    """All finite Capon heatmap frames of one recording, flattened to (N, 5120)."""
    try:
        from rerun.recording import load_recording
    except ImportError:  # rerun-sdk < 0.28
        load_recording = rr.dataframe.load_recording
    recording = load_recording(str(DATA_DIR / f"{name}.rrd"))
    view = recording.view(index="timestamp", contents="radar/heatmap_3d")
    table = view.select().read_all()
    frames = []
    for batch in table.column("/radar/heatmap_3d:Tensor:data"):
        for item in batch:
            if item is None:
                continue
            arr = np.array(item["buffer"].as_py(), dtype=np.float32)
            # a couple of frames per capture are corrupt (NaN / float32-max noise)
            if np.isfinite(arr).all() and np.abs(arr).max() < 1e12:
                frames.append(arr)
    return np.array(frames)


def main():
    parser = argparse.ArgumentParser(description="Classify the shipped material recordings")
    parser.add_argument("--view", choices=MATERIALS, default="plastic_sheet",
                        help="recording to open in the Rerun viewer")
    parser.add_argument("--no-viewer", action="store_true", help="skip the Rerun viewer")
    args = parser.parse_args()

    if not args.no_viewer:
        rr.init("material_classification", spawn=True)
        rr.log_file_from_path(DATA_DIR / f"{args.view}.rrd")
        print(f"Rerun viewer opened with {args.view}.rrd — select radar/heatmap_3d.\n")

    print("Loading the three recordings and extracting Capon heatmap fingerprints...")
    data = {name: np.log10(load_heatmaps(name) + 1) for name in MATERIALS}
    for name, X in data.items():
        print(f"  {name:14s} {len(X):3d} frames of 10x32x16")

    # Train on the first half of each capture, classify the second half.
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    Xtr, ytr, Xte, yte = [], [], [], []
    for label, (name, X) in enumerate(data.items()):
        half = len(X) // 2
        Xtr.append(X[:half]); ytr += [label] * half
        Xte.append(X[half:]); yte += [label] * (len(X) - half)
    scaler = StandardScaler().fit(np.vstack(Xtr))
    clf = LogisticRegression(max_iter=2000).fit(scaler.transform(np.vstack(Xtr)), ytr)

    print("\nTrained on the first half of each capture — classifying the second half:")
    preds = clf.predict(scaler.transform(np.vstack(Xte)))
    yte = np.array(yte)
    for label, name in enumerate(MATERIALS):
        mask = yte == label
        acc = (preds[mask] == label).mean()
        print(f"  {name:14s} {acc*100:5.1f}% of {mask.sum()} held-out frames correct")
    print(f"  {'overall':14s} {(preds == yte).mean()*100:5.1f}%")
    print("\nSame physics, bigger scale: the PyTorch network in ML/ reaches 98.8%")
    print("across 9 multilayer wall classes on its own recording campaign.")


if __name__ == "__main__":
    main()
