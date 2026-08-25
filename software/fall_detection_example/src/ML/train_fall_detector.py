"""
train_fall_detector.py  (v2 - temporal window approach)
Key insight: a fall is a TEMPORAL PATTERN, not a single-frame state.
  - z features dropped (elevation resolution too low)
  - All features describe the SHAPE of signal over N frames
  - CNN uses a CAUSAL sliding window (label at END of window)
  - Both models look for: high Doppler burst -> sudden silence

Window (N=30 frames @ ~10fps = 3 seconds):
  frames 0..9   = early  (pre-fall baseline)
  frames 10..19 = mid    (burst happens here)
  frames 20..29 = late   (silence if person is now lying still)
"""

import os, glob, json, argparse
import numpy as np
import pandas as pd
from pathlib import Path

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

WINDOW_N  = 30
EARLY_END = 10
MID_END   = 20

FRAME_COLS = [
    "doppler_mean", "doppler_max", "doppler_std", "doppler_post",
    "point_count", "bbox_width", "aspect_ratio",
    "centroid_z", "z_variance",
]

WINDOW_FEATURE_NAMES = [
    "burst_ratio", "silence_ratio", "decay_ratio",
    "peak_val", "peak_pos_norm", "peak_sharpness", "post_peak_mean",
    "e_early", "e_mid", "e_late",
    "pts_early_mean", "pts_late_mean", "pts_ratio",
    "early_dstd", "mid_dstd", "late_dstd", "stillness",
    "slope",
    "dmax_global", "dmean_global", "dstd_global",
]


def window_features(w: np.ndarray) -> np.ndarray:
    """
    w: (WINDOW_N, len(FRAME_COLS))
    Returns 1D float32 feature vector capturing burst->silence.
    """
    w = np.nan_to_num(w, nan=0.0)

    dmax_idx  = FRAME_COLS.index("doppler_max")
    dmean_idx = FRAME_COLS.index("doppler_mean")
    pts_idx   = FRAME_COLS.index("point_count")

    dmax  = w[:, dmax_idx]
    dmean = w[:, dmean_idx]
    pts   = w[:, pts_idx]

    # Energy per phase
    e_early = float(np.mean(dmax[:EARLY_END]))
    e_mid   = float(np.mean(dmax[EARLY_END:MID_END]))
    e_late  = float(np.mean(dmax[MID_END:]))

    # Burst/silence ratios
    burst_ratio   = e_mid  / (e_early + 1e-6)
    silence_ratio = e_late / (e_early + 1e-6)
    decay_ratio   = e_late / (e_mid   + 1e-6)

    # Peak characteristics
    peak_frame     = float(np.argmax(dmax))
    peak_val       = float(np.max(dmax))
    peak_pos_norm  = peak_frame / max(WINDOW_N - 1, 1)
    post_peak      = dmax[int(peak_frame)+1:]
    post_peak_mean = float(np.mean(post_peak)) if len(post_peak) > 0 else 0.0
    peak_sharpness = peak_val / (post_peak_mean + 1e-6)

    # Point count dynamics
    pts_early_mean = float(np.mean(pts[:EARLY_END]))
    pts_late_mean  = float(np.mean(pts[MID_END:]))
    pts_ratio      = pts_late_mean / (pts_early_mean + 1e-6)

    # Doppler spread per phase
    early_dstd = float(np.std(dmax[:EARLY_END]))
    mid_dstd   = float(np.std(dmax[EARLY_END:MID_END]))
    late_dstd  = float(np.std(dmax[MID_END:]))
    stillness  = 1.0 / (late_dstd + 1e-3)

    # End-of-window trend (negative = Doppler dropping)
    x_axis = np.arange(10, dtype=np.float32)
    slope  = float(np.polyfit(x_axis, dmax[-10:], 1)[0])

    # Global stats
    dmax_global  = float(np.max(dmax))
    dmean_global = float(np.mean(dmean))
    dstd_global  = float(np.std(dmax))

    return np.array([
        burst_ratio, silence_ratio, decay_ratio,
        peak_val, peak_pos_norm, peak_sharpness, post_peak_mean,
        e_early, e_mid, e_late,
        pts_early_mean, pts_late_mean, pts_ratio,
        early_dstd, mid_dstd, late_dstd, stillness,
        slope,
        dmax_global, dmean_global, dstd_global,
    ], dtype=np.float32)


def load_windowed_tabular(sessions_dir: str):
    X_all, y_all, g_all = [], [], []
    for sess_id, path in enumerate(sorted(glob.glob(
            os.path.join(sessions_dir, "*_labeled.csv")))):
        df = pd.read_csv(path)
        for col in FRAME_COLS:
            if col not in df.columns:
                df[col] = 0.0
        df[FRAME_COLS] = df[FRAME_COLS].fillna(0.0)
        vals   = df[FRAME_COLS].values.astype(np.float32)
        labels = df["label"].values
        for start in range(len(df) - WINDOW_N + 1):
            end = start + WINDOW_N
            lbl = int(labels[start + WINDOW_N//2 : end].max())
            X_all.append(window_features(vals[start:end]))
            y_all.append(lbl)
            g_all.append(sess_id)
    X = np.stack(X_all).astype(np.float32)
    y = np.array(y_all, dtype=np.int8)
    g = np.array(g_all)
    print(f"[Tabular windows] {X.shape}  | Fall: {y.sum()} ({100*y.mean():.1f}%)")
    return X, y, g


def load_windowed_microdoppler(sessions_dir: str):
    X_all, y_all, g_all = [], [], []
    for sess_id, md_path in enumerate(sorted(glob.glob(
            os.path.join(sessions_dir, "*_microdoppler.npy")))):
        lbl_path = md_path.replace("_microdoppler.npy", "_microdoppler_labels.npy")
        if not os.path.exists(lbl_path):
            continue
        spectra = np.load(md_path)
        labels  = np.load(lbl_path)
        if len(spectra) < WINDOW_N:
            continue
        for start in range(len(spectra) - WINDOW_N + 1):
            end = start + WINDOW_N
            lbl = int(labels[start + WINDOW_N//2 : end].max())
            X_all.append(spectra[start:end])
            y_all.append(lbl)
            g_all.append(sess_id)
    if not X_all:
        return None, None, None
    X = np.stack(X_all).astype(np.float32)
    y = np.array(y_all, dtype=np.int8)
    g = np.array(g_all)
    print(f"[MD windows]      {X.shape}  | Fall: {y.sum()} ({100*y.mean():.1f}%)")
    return X, y, g


def train_xgboost(X, y, groups, save_dir: str):
    from xgboost import XGBClassifier
    from sklearn.model_selection import GroupKFold, cross_validate

    print("\n" + "="*55)
    print("XGBoost  --  temporal window features")
    print("="*55)

    neg, pos = (y==0).sum(), (y==1).sum()
    spw = neg / max(pos, 1)
    print(f"  scale_pos_weight = {spw:.1f}")

    model = XGBClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=spw, eval_metric="aucpr",
        random_state=42, n_jobs=-1,
    )

    n_splits = max(2, min(5, len(np.unique(groups[y==1]))))
    gkf = GroupKFold(n_splits=n_splits)
    cv  = cross_validate(model, X, y, groups=groups, cv=gkf,
                         scoring=["f1", "roc_auc", "average_precision"])

    print(f"  CV F1     : {cv['test_f1'].mean():.3f} +/- {cv['test_f1'].std():.3f}")
    print(f"  CV ROC-AUC: {cv['test_roc_auc'].mean():.3f} +/- {cv['test_roc_auc'].std():.3f}")
    print(f"  CV PR-AUC : {cv['test_average_precision'].mean():.3f} +/- {cv['test_average_precision'].std():.3f}")

    model.fit(X, y)

    imp = sorted(zip(WINDOW_FEATURE_NAMES, model.feature_importances_), key=lambda x: -x[1])
    print("\n  Feature importances (top 10):")
    for feat, score in imp[:10]:
        print(f"    {'|'*int(score*50)} {feat} {score:.3f}")

    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, "xgb_fall.json")
    model.save_model(path)
    print(f"\n  Saved -> {path}")
    return model


def build_cnn(num_bins: int, window: int):
    import torch.nn as nn
    class FallCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                # Wide time kernel to capture temporal transitions
                nn.Conv2d(1, 16, kernel_size=(5, 3), padding=(2, 1)),
                nn.BatchNorm2d(16), nn.ReLU(),
                nn.MaxPool2d((2, 2)),
                nn.Conv2d(16, 32, kernel_size=(5, 3), padding=(2, 1)),
                nn.BatchNorm2d(32), nn.ReLU(),
                nn.MaxPool2d((2, 2)),
                nn.Conv2d(32, 64, kernel_size=(3, 3), padding=(1, 1)),
                nn.BatchNorm2d(64), nn.ReLU(),
                nn.AdaptiveAvgPool2d((4, 1)),
            )
            self.head = nn.Sequential(
                nn.Flatten(),
                nn.Linear(64*4, 128), nn.ReLU(), nn.Dropout(0.4),
                nn.Linear(128, 32),   nn.ReLU(), nn.Dropout(0.2),
                nn.Linear(32, 1),
            )
        def forward(self, x):
            return self.head(self.net(x.unsqueeze(1))).squeeze(1)
    return FallCNN()


def train_cnn(X_md, y_md, groups, save_dir: str, epochs: int = 50):
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
        from sklearn.model_selection import GroupKFold
        from sklearn.metrics import f1_score, roc_auc_score
    except ImportError:
        print("[CNN] PyTorch not found: pip install torch")
        return None

    print("\n" + "="*55)
    print("CNN  --  causal micro-Doppler windows")
    print("="*55)

    device   = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    window   = X_md.shape[1]
    num_bins = X_md.shape[2]
    print(f"  Device: {device}  Window: {window}  Bins: {num_bins}")

    mean = X_md.mean(axis=(0,1), keepdims=True)
    std  = X_md.std( axis=(0,1), keepdims=True) + 1e-6
    X_n  = (X_md - mean) / std

    n_splits = max(2, min(5, len(np.unique(groups[y_md==1]))))
    gkf = GroupKFold(n_splits=n_splits)
    fold_f1s, fold_aucs = [], []

    for fold, (tr, va) in enumerate(gkf.split(X_n, y_md, groups)):
        Xtr = torch.tensor(X_n[tr]); ytr = torch.tensor(y_md[tr].astype(np.float32))
        Xva = torch.tensor(X_n[va]); yva = y_md[va]
        pos_w = torch.tensor([(ytr==0).sum() / max((ytr==1).sum(), 1)])
        mdl = build_cnn(num_bins, window).to(device)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_w.to(device))
        opt   = torch.optim.AdamW(mdl.parameters(), lr=1e-3, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
        loader = DataLoader(TensorDataset(Xtr, ytr), batch_size=32, shuffle=True)
        for _ in range(epochs):
            mdl.train()
            for xb, yb in loader:
                xb, yb = xb.to(device), yb.to(device)
                opt.zero_grad(); loss_fn(mdl(xb), yb).backward(); opt.step()
            sched.step()  # step per epoch, not per batch
        mdl.eval()
        with torch.no_grad():
            logits = mdl(Xva.to(device)).cpu().numpy()
        probs = 1/(1+np.exp(-logits)); preds = (probs>0.5).astype(int)
        f1  = f1_score(yva, preds, zero_division=0)
        auc = roc_auc_score(yva, probs) if len(np.unique(yva)) > 1 else 0.0
        fold_f1s.append(f1); fold_aucs.append(auc)
        print(f"  Fold {fold+1}: F1={f1:.3f}  AUC={auc:.3f}")

    print(f"\n  CV F1 : {np.mean(fold_f1s):.3f} +/- {np.std(fold_f1s):.3f}")
    print(f"  CV AUC: {np.mean(fold_aucs):.3f} +/- {np.std(fold_aucs):.3f}")

    # Final model
    X_t = torch.tensor(X_n); y_t = torch.tensor(y_md.astype(np.float32))
    pos_w = torch.tensor([(y_t==0).sum() / max((y_t==1).sum(), 1)])
    final = build_cnn(num_bins, window).to(device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_w.to(device))
    opt   = torch.optim.AdamW(final.parameters(), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    loader = DataLoader(TensorDataset(X_t, y_t), batch_size=32, shuffle=True)
    for ep in range(epochs):
        final.train()
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad(); loss_fn(final(xb), yb).backward(); opt.step()
        sched.step()  # step per epoch
        final.train()
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad(); loss_fn(final(xb), yb).backward(); opt.step(); sched.step()
        if (ep+1) % 10 == 0:
            print(f"  Final model epoch {ep+1}/{epochs}")

    os.makedirs(save_dir, exist_ok=True)
    torch.save(final.state_dict(), os.path.join(save_dir, "cnn_fall.pt"))
    np.savez(os.path.join(save_dir, "cnn_norm.npz"),
             mean=mean, std=std, window=np.array(window), num_bins=np.array(num_bins))
    print(f"  Saved -> {save_dir}/cnn_fall.pt")
    return final, mean, std


def train_fusion(xgb_model, cnn_result, X_tab, y_tab, g_tab, X_md, y_md, g_md, save_dir):
    try:
        import torch
        from sklearn.metrics import f1_score, roc_auc_score
    except ImportError:
        return

    print("\n" + "="*55)
    print("Late fusion  --  grid search blend weight")
    print("="*55)

    cnn_model, mean, std = cnn_result
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    p_xgb = xgb_model.predict_proba(X_tab)[:, 1]
    X_n   = (X_md - mean) / (std + 1e-6)
    X_t   = torch.tensor(X_n)
    cnn_model.eval()
    with torch.no_grad():
        logits = np.concatenate([
            cnn_model(X_t[i:i+256].to(device)).cpu().numpy()
            for i in range(0, len(X_t), 256)
        ])
    p_cnn = 1 / (1 + np.exp(-logits))

    n = min(len(p_xgb), len(p_cnn))
    p_xgb = p_xgb[:n]; p_cnn = p_cnn[:n]; y_ref = y_tab[:n]

    best_alpha, best_f1 = 0.5, 0.0
    print(f"  {'alpha':>6} {'F1':>7} {'AUC':>7}")
    for alpha in np.linspace(0, 1, 11):
        p_f = alpha * p_xgb + (1-alpha) * p_cnn
        f1  = f1_score(y_ref, (p_f>0.5).astype(int), zero_division=0)
        auc = roc_auc_score(y_ref, p_f) if len(np.unique(y_ref)) > 1 else 0.0
        mark = " <--" if f1 > best_f1 else ""
        print(f"  {alpha:>6.1f} {f1:>7.3f} {auc:>7.3f}{mark}")
        if f1 > best_f1:
            best_f1, best_alpha = f1, alpha

    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, "fusion_weights.json"), "w") as f:
        json.dump({"alpha": best_alpha, "xgb_weight": best_alpha,
                   "cnn_weight": 1-best_alpha, "fusion_f1": best_f1,
                   "window_n": WINDOW_N}, f, indent=2)
    print(f"  Best alpha={best_alpha:.1f}  F1={best_f1:.3f}")
    print(f"  Saved -> {save_dir}/fusion_weights.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", default="data/sessions/")
    parser.add_argument("--models",   default="models/")
    parser.add_argument("--epochs",   type=int, default=50)
    parser.add_argument("--no-cnn",   action="store_true")
    args = parser.parse_args()

    print(f"Sessions: {args.sessions}  |  Window N: {WINDOW_N} frames")

    X_tab, y_tab, g_tab = load_windowed_tabular(args.sessions)
    xgb_model = train_xgboost(X_tab, y_tab, g_tab, args.models)

    cnn_result = None
    X_md = y_md = g_md = None
    if not args.no_cnn:
        X_md, y_md, g_md = load_windowed_microdoppler(args.sessions)
        if X_md is not None:
            cnn_result = train_cnn(X_md, y_md, g_md, args.models, args.epochs)

    if cnn_result is not None and X_md is not None:
        train_fusion(xgb_model, cnn_result,
                     X_tab, y_tab, g_tab,
                     X_md,  y_md,  g_md, args.models)

    print("\nDone. Models saved:")
    for fp in sorted(glob.glob(os.path.join(args.models, "*"))):
        print(f"  {Path(fp).name:<35} {os.path.getsize(fp)/1024:6.1f} KB")


if __name__ == "__main__":
    main()