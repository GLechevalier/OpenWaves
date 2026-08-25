"""
diagnose.py — Dataset diagnosis and model evaluation for fall detection.

Usage
─────
  python diagnose.py --sessions data/sessions/
  python diagnose.py --sessions data/sessions/ --models models/
  python diagnose.py --sessions data/sessions/ --relabel --pre 1.0 --post 3.0
"""

import os
import glob
import json
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

FEATURE_COLS = [
    "centroid_z", "centroid_z_min", "centroid_z_max", "z_variance",
    "bbox_height", "bbox_width", "aspect_ratio",
    "doppler_mean", "doppler_max", "doppler_std",
    "point_count",
    "delta_z", "delta_z_rate", "doppler_post", "window_z_std",
]

# ─────────────────────────────────────────────────────────────────
# Key insight: a fall is a TRANSITION over 10-20 frames, not a state.
# mean_z during fall frames is meaningless — it averages standing +
# mid-fall + lying, giving a value close to normal standing height.
# The correct metric is the z DROP across each contiguous fall event.
# ─────────────────────────────────────────────────────────────────

def _z_drop(df: pd.DataFrame) -> float:
    """
    For each contiguous block of label==1 frames, compute:
        drop = mean_z(last 3 frames) - mean_z(first 3 frames)
    A fall shows a negative drop (person descended).
    Returns the mean drop across all events in this session.
    """
    z      = df["centroid_z"].values
    labels = df["label"].values
    drops  = []

    in_fall, start = False, 0
    for i in range(len(labels)):
        if labels[i] == 1 and not in_fall:
            in_fall, start = True, i
        elif labels[i] == 0 and in_fall:
            in_fall = False
            seg = z[start:i]
            seg = seg[~np.isnan(seg)]
            if len(seg) >= 6:
                drops.append(seg[-3:].mean() - seg[:3].mean())

    if in_fall:                          # fall at end of session
        seg = z[start:]
        seg = seg[~np.isnan(seg)]
        if len(seg) >= 6:
            drops.append(seg[-3:].mean() - seg[:3].mean())

    return round(float(np.mean(drops)), 3) if drops else float("nan")


def _count_fall_events(df: pd.DataFrame) -> int:
    """Count distinct contiguous fall windows."""
    labels = df["label"].values
    count, in_fall = 0, False
    for lab in labels:
        if lab == 1 and not in_fall:
            count  += 1
            in_fall = True
        elif lab == 0:
            in_fall = False
    return count


# ─────────────────────────────────────────────────────────────────
# 1. Dataset diagnosis
# ─────────────────────────────────────────────────────────────────

def diagnose_dataset(sessions_dir: str):
    csv_paths = sorted(glob.glob(os.path.join(sessions_dir, "*_labeled.csv")))
    if not csv_paths:
        print(f"No *_labeled.csv files found in {sessions_dir}")
        return None

    print("\n" + "="*70)
    print("DATASET DIAGNOSIS")
    print("="*70)
    print("  z_drop    = z[last 3 fall frames] - z[first 3 fall frames] per event")
    print("              negative = person descended (GOOD), ~0 = radar can't see it")
    print("  dz_rate   = most negative delta_z_rate frame during fall (m/s)")
    print("              should be < -0.3 for a real fall signal")
    print("="*70)

    rows = []
    for path in csv_paths:
        df   = pd.read_csv(path)
        name = Path(path).stem.replace("_labeled", "")
        parts  = name.split("_")
        action = "_".join(parts[1:-1]) if len(parts) > 2 else name

        total       = len(df)
        valid       = df.dropna(subset=["centroid_z"])
        fall_frames = int(df["label"].sum())
        valid_falls = int(valid["label"].sum())
        n_events    = _count_fall_events(valid)

        z_drop = _z_drop(valid)

        if valid_falls > 0 and "delta_z_rate" in valid.columns:
            fall_dz = valid[valid["label"] == 1]["delta_z_rate"].dropna()
            peak_dz = round(fall_dz.min(), 3) if len(fall_dz) else float("nan")
        else:
            peak_dz = float("nan")

        rows.append({
            "session":      name[-22:],
            "action":       action,
            "frames":       total,
            "fall_frames":  fall_frames,
            "n_events":     n_events,       # how many distinct falls
            "z_drop(m)":    z_drop,         # negative = good
            "peak_dz_rate": peak_dz,        # negative = good
        })

    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False))

    total_frames = summary["frames"].sum()
    total_falls  = summary["fall_frames"].sum()
    print(f"\n  Total frames      : {total_frames}")
    print(f"  Total fall frames : {total_falls} ({100*total_falls/max(total_frames,1):.1f}%)")
    print(f"  Total fall events : {summary['n_events'].sum()}")
    print(f"  Sessions          : {len(summary)}")

    print("\n  Warnings:")

    no_falls = summary[summary["fall_frames"] == 0]
    if len(no_falls):
        print(f"  ⚠  {len(no_falls)} sessions have 0 fall frames (ADL sessions — OK if intentional)")

    # The key diagnostic: is z_drop actually negative?
    fall_sessions = summary[summary["fall_frames"] > 0]
    if len(fall_sessions):
        mean_drop = fall_sessions["z_drop(m)"].dropna().mean()
        if np.isnan(mean_drop):
            print("  ⚠  z_drop could not be computed — fall windows too short (< 6 frames)")
        elif mean_drop > -0.05:
            print(f"  ✗  CRITICAL: mean z_drop = {mean_drop:.3f} m  (want < -0.3 m)")
            print("     The radar cannot distinguish standing from lying.")
            print("     → Check radar tilt angle (should be 15-30 deg downward)")
            print("     → Check cfg: elevation must be enabled (channelCfg second value = 7)")
        elif mean_drop > -0.3:
            print("  ⚠  z_drop = {mean_drop:.3f} m — weak signal (want < -0.3 m)")
            print("     Try increasing radar tilt angle.")
        else:
            print("  ✓  z_drop = {mean_drop:.3f} m — good height separation")

        mean_dz = fall_sessions["peak_dz_rate"].dropna().mean()
        if not np.isnan(mean_dz):
            if mean_dz > -0.1:
                print(f"  ✗  CRITICAL: peak delta_z_rate = {mean_dz:.3f} m/s during falls")
                print("     No velocity drop detected — z_rate feature is blind to falls")
            elif mean_dz > -0.3:
                print(f"  ⚠  peak delta_z_rate = {mean_dz:.3f} m/s — weak (want < -0.3)")
            else:
                print(f"  ✓  peak delta_z_rate = {mean_dz:.3f} m/s — good fall velocity signal")

    if total_falls < 200:
        print(f"  ⚠  Only {total_falls} fall frames. Need 200+ for reliable training.")
        print("     Run: python diagnose.py --relabel --pre 1.0 --post 3.0")
    else:
        print(f"  ✓  {total_falls} fall frames — sufficient for training")

    return summary


# ─────────────────────────────────────────────────────────────────
# 2. Re-label with wider window
# ─────────────────────────────────────────────────────────────────

def relabel_sessions(sessions_dir: str, pre_fall_s: float = 1.0, post_fall_s: float = 3.0):
    import csv

    meta_paths = sorted(glob.glob(os.path.join(sessions_dir, "*_meta.json")))
    print(f"\nRe-labeling {len(meta_paths)} sessions (pre={pre_fall_s}s, post={post_fall_s}s)...")

    for meta_path in meta_paths:
        with open(meta_path) as f:
            meta = json.load(f)

        fall_stamps = meta.get("fall_timestamps", [])
        base        = meta_path.replace("_meta.json", "")
        jsonl_path  = base + ".jsonl"
        csv_path    = base + "_labeled.csv"

        if not os.path.exists(jsonl_path):
            continue

        rows = []
        with open(jsonl_path) as f:
            for line in f:
                rows.append(json.loads(line))

        fieldnames = ["frame_idx", "t", "numPts", "posture"] + FEATURE_COLS + ["label"]
        fall_count = 0

        with open(csv_path, "w", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                label = 0
                for tf in fall_stamps:
                    if tf - pre_fall_s <= r["t"] <= tf + post_fall_s:
                        label = 1
                        break
                fall_count += label
                row = {k: r.get(k, float("nan")) for k in fieldnames}
                row["label"] = label
                writer.writerow(row)

        print(f"  {Path(base).name[-45:]:<45} → {fall_count} fall frames")

    print("Done.")


# ─────────────────────────────────────────────────────────────────
# 3. Model evaluation
# ─────────────────────────────────────────────────────────────────

def evaluate_models(sessions_dir: str, models_dir: str):
    from xgboost import XGBClassifier
    from sklearn.metrics import (confusion_matrix,
                                 roc_auc_score, average_precision_score,
                                 precision_recall_fscore_support)

    print("\n" + "="*60)
    print("MODEL EVALUATION (leave-one-session-out)")
    print("="*60)

    csv_paths = sorted(glob.glob(os.path.join(sessions_dir, "*_labeled.csv")))
    dfs = []
    for i, p in enumerate(csv_paths):
        df = pd.read_csv(p)
        df["session_id"] = i
        parts = Path(p).stem.replace("_labeled","").split("_")
        df["action"] = "_".join(parts[1:-1])
        dfs.append(df)

    data    = pd.concat(dfs, ignore_index=True).dropna(subset=["centroid_z"])
    X       = data[FEATURE_COLS].values.astype(np.float32)
    y       = data["label"].values
    groups  = data["session_id"].values
    actions = data["action"].values

    all_probs = np.full(len(y), np.nan)
    for sess in np.unique(groups):
        mask_val = groups == sess
        mask_tr  = ~mask_val
        if y[mask_tr].sum() == 0:
            continue

        neg, pos = (y[mask_tr]==0).sum(), (y[mask_tr]==1).sum()
        m = XGBClassifier(n_estimators=400, max_depth=5, learning_rate=0.05,
                          scale_pos_weight=neg/max(pos,1), eval_metric="aucpr",
                          random_state=42, n_jobs=-1)
        m.fit(X[mask_tr], y[mask_tr])
        all_probs[mask_val] = m.predict_proba(X[mask_val])[:, 1]

    valid = ~np.isnan(all_probs)
    y_v   = y[valid]
    p_v   = all_probs[valid]

    print("\n  Threshold sweep:")
    print(f"  {'Thresh':>7} {'Prec':>7} {'Recall':>8} {'F1':>6} {'FalseAlarm%':>12} {'MissRate%':>10}")
    print(f"  {'-'*56}")
    for thresh in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        pred = (p_v > thresh).astype(int)
        pr, re, f1, _ = precision_recall_fscore_support(
            y_v, pred, average="binary", zero_division=0)
        fa   = 100 * ((pred==1) & (y_v==0)).sum() / max((y_v==0).sum(), 1)
        miss = 100 * ((pred==0) & (y_v==1)).sum() / max((y_v==1).sum(), 1)
        best = " <-- recommended" if thresh == 0.3 else ""
        print(f"  {thresh:>7.1f} {pr:>7.3f} {re:>8.3f} {f1:>6.3f} {fa:>11.1f}% {miss:>9.1f}%{best}")

    if len(np.unique(y_v)) > 1:
        auc = roc_auc_score(y_v, p_v)
        pr_auc = average_precision_score(y_v, p_v)
        print(f"\n  ROC-AUC : {auc:.3f}")
        print(f"  PR-AUC  : {pr_auc:.3f}  (most meaningful with imbalanced data)")

    pred05 = (p_v > 0.5).astype(int)
    cm = confusion_matrix(y_v, pred05)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0,0,0,0)
    print("\n  Confusion matrix (threshold=0.5):")
    print("                  Predicted")
    print("                  Normal   Fall")
    print(f"  Actual Normal   {tn:6d}  {fp:5d}   ← false alarms")
    print(f"  Actual Fall     {fn:6d}  {tp:5d}   ← missed falls")

    print("\n  Per-action breakdown:")
    print(f"  {'Action':<20} {'Frames':>7} {'Falls':>6} {'Recall':>8} {'FalseAlarm%':>12}")
    print(f"  {'-'*56}")
    for action in sorted(np.unique(actions[valid])):
        mask = actions[valid] == action
        yy   = y_v[mask]
        pp   = pred05[mask]
        recall = yy[pp==1].sum() / max(yy.sum(), 1)
        fa     = 100 * ((pp==1) & (yy==0)).sum() / max((yy==0).sum(), 1)
        print(f"  {action:<20} {mask.sum():>7} {int(yy.sum()):>6} {recall:>8.3f} {fa:>11.1f}%")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", default="data/sessions/")
    parser.add_argument("--models",   default=None)
    parser.add_argument("--relabel",  action="store_true")
    parser.add_argument("--pre",      type=float, default=1.0)
    parser.add_argument("--post",     type=float, default=3.0)
    args = parser.parse_args()

    diagnose_dataset(args.sessions)

    if args.relabel:
        relabel_sessions(args.sessions, args.pre, args.post)
        print("\nRe-running diagnosis after relabeling...")
        diagnose_dataset(args.sessions)

    if args.models and os.path.exists(os.path.join(args.models, "xgb_fall.json")):
        evaluate_models(args.sessions, args.models)


if __name__ == "__main__":
    main()