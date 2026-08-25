"""
fall_detector_live.py
──────────────────────────────────────────────────────────────────
Real-time fall detection using trained XGBoost + CNN models.
Sends instant alerts to your phone via a live web UI.

Phone UI  ->  http://<your-pc-ip>:8766
  - Live radar status (green = normal, red = FALL DETECTED)
  - Alert history with timestamps
  - Mute / test buttons

Usage
─────
  python fall_detector_live.py
  python fall_detector_live.py --models models/ --threshold 0.45

Requirements
────────────
  pip install xgboost torch numpy
"""

import os
import sys
import json
import threading
import collections
import math
import numpy as np

sys.path.append(os.getcwd())
sys.path.append(r'C:\ti\radar_toolbox_3_20_00_04\tools\visualizers\Applications_Visualizer\common')
sys.path.append(r'C:\ti\radar_toolbox_3_20_00_04\tools\mmwave_data_recorder\src')


class FallDetector:
    # ─────────────────────────────────────────────────────────────────
    # Config — must match training script exactly
    # ─────────────────────────────────────────────────────────────────

    EARLY_END = 10
    MID_END   = 20

    FRAME_COLS = [
        "doppler_mean", "doppler_max", "doppler_std", "doppler_post",
        "point_count", "bbox_width", "aspect_ratio",
        "centroid_z", "z_variance",
    ]

    def __init__(self, models_dir, threshold, window_N =30):

        self.window_N = window_N
        self.threshold = threshold

        # Rolling buffers (thread-safe via lock)
        self._buf_lock    = threading.Lock()
        self._frame_buf   = collections.deque(maxlen=self.window_N)   # tabular rows
        self._md_buf      = collections.deque(maxlen=self.window_N)   # MD spectra

        # Alert state
        self._alerts: list[dict] = []          # list of {t, p_xgb, p_cnn, p_fused}
        self._current_prob = 0.0               # latest fused probability
        self._muted        = False
        self._stop_flag    = threading.Event()

        # SSE clients waiting for push events
        self._sse_clients: list = []
        self._sse_lock    = threading.Lock()

        self.models_dir = models_dir
        self.load_models()

        return


    # ─────────────────────────────────────────────────────────────────
    # Feature extraction (identical to radar_record.py)
    # ─────────────────────────────────────────────────────────────────

    def extract_frame_features(self, pc: np.ndarray, pc_list: list, t_list: list) -> dict:
        nan = float("nan")
        cols = {k: nan for k in self.FRAME_COLS}

        if pc is None or len(pc) == 0:
            return cols

        z  = pc[:, 2]
        dv = np.abs(pc[:, 3])

        bw = float(max(np.max(pc[:,0]) - np.min(pc[:,0]),
                    np.max(pc[:,1]) - np.min(pc[:,1])))
        bh = float(np.max(z) - np.min(z))

        cols["doppler_mean"] = float(np.mean(dv))
        cols["doppler_max"]  = float(np.max(dv))
        cols["doppler_std"]  = float(np.std(dv))
        cols["point_count"]  = float(len(pc))
        cols["bbox_width"]   = bw
        cols["aspect_ratio"] = bh / bw if bw > 0.01 else nan
        cols["centroid_z"]   = float(np.mean(z))
        cols["z_variance"]   = float(np.var(z))

        if len(pc_list) >= 3:
            post_frames = pc_list[-3:]
            post_dv = np.concatenate([np.abs(p[:,3]) for p in post_frames if len(p) > 0])
            cols["doppler_post"] = float(np.mean(post_dv)) if len(post_dv) > 0 else nan
        else:
            cols["doppler_post"] = nan

        return cols


    # ─────────────────────────────────────────────────────────────────
    # Window feature extraction (identical to train_fall_detector.py)
    # ─────────────────────────────────────────────────────────────────

    def window_features(self, w: np.ndarray) -> np.ndarray:
        w = np.nan_to_num(w, nan=0.0)

        dmax_idx  = self.FRAME_COLS.index("doppler_max")
        dmean_idx = self.FRAME_COLS.index("doppler_mean")
        pts_idx   = self.FRAME_COLS.index("point_count")

        dmax  = w[:, dmax_idx]
        dmean = w[:, dmean_idx]
        pts   = w[:, pts_idx]

        e_early = float(np.mean(dmax[:self.EARLY_END]))
        e_mid   = float(np.mean(dmax[self.EARLY_END:self.MID_END]))
        e_late  = float(np.mean(dmax[self.MID_END:]))

        burst_ratio   = e_mid  / (e_early + 1e-6)
        silence_ratio = e_late / (e_early + 1e-6)
        decay_ratio   = e_late / (e_mid   + 1e-6)

        peak_frame     = float(np.argmax(dmax))
        peak_val       = float(np.max(dmax))
        peak_pos_norm  = peak_frame / max(self.window_N - 1, 1)
        post_peak      = dmax[int(peak_frame)+1:]
        post_peak_mean = float(np.mean(post_peak)) if len(post_peak) > 0 else 0.0
        peak_sharpness = peak_val / (post_peak_mean + 1e-6)

        pts_early_mean = float(np.mean(pts[:self.EARLY_END]))
        pts_late_mean  = float(np.mean(pts[self.MID_END:]))
        pts_ratio      = pts_late_mean / (pts_early_mean + 1e-6)

        early_dstd = float(np.std(dmax[:self.EARLY_END]))
        mid_dstd   = float(np.std(dmax[self.EARLY_END:self.MID_END]))
        late_dstd  = float(np.std(dmax[self.MID_END:]))
        stillness  = 1.0 / (late_dstd + 1e-3)

        slope = float(np.polyfit(np.arange(10, dtype=np.float32), dmax[-10:], 1)[0])

        return np.array([
            burst_ratio, silence_ratio, decay_ratio,
            peak_val, peak_pos_norm, peak_sharpness, post_peak_mean,
            e_early, e_mid, e_late,
            pts_early_mean, pts_late_mean, pts_ratio,
            early_dstd, mid_dstd, late_dstd, stillness,
            slope,
            float(np.max(dmax)), float(np.mean(dmean)), float(np.std(dmax)),
        ], dtype=np.float32)


    # ─────────────────────────────────────────────────────────────────
    # Model loading
    # ─────────────────────────────────────────────────────────────────

    def load_models(self):
        from xgboost import XGBClassifier
        models_dir = self.models_dir
        xgb = XGBClassifier()
        xgb.load_model(os.path.join(models_dir, "xgb_fall.json"))
        print("  [Models] XGBoost loaded")

        cnn = cnn_mean = cnn_std = None
        cnn_window = cnn_bins = 0

        try:
            import torch
            norm = np.load(os.path.join(models_dir, "cnn_norm.npz"))
            cnn_mean   = norm["mean"]
            cnn_std    = norm["std"]
            cnn_window = int(norm["window"])
            cnn_bins   = int(norm["num_bins"])

            # Rebuild CNN architecture
            import torch.nn as nn
            class FallCNN(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.net = nn.Sequential(
                        nn.Conv2d(1, 16, kernel_size=(5,3), padding=(2,1)),
                        nn.BatchNorm2d(16), nn.ReLU(), nn.MaxPool2d((2,2)),
                        nn.Conv2d(16, 32, kernel_size=(5,3), padding=(2,1)),
                        nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d((2,2)),
                        nn.Conv2d(32, 64, kernel_size=(3,3), padding=(1,1)),
                        nn.BatchNorm2d(64), nn.ReLU(),
                        nn.AdaptiveAvgPool2d((4,1)),
                    )
                    self.head = nn.Sequential(
                        nn.Flatten(),
                        nn.Linear(64*4, 128), nn.ReLU(), nn.Dropout(0.4),
                        nn.Linear(128, 32),   nn.ReLU(), nn.Dropout(0.2),
                        nn.Linear(32, 1),
                    )
                def forward(self, x):
                    return self.head(self.net(x.unsqueeze(1))).squeeze(1)

            cnn = FallCNN()
            cnn.load_state_dict(torch.load(
                os.path.join(models_dir, "cnn_fall.pt"), map_location="cpu"))
            cnn.eval()
            print(f"  [Models] CNN loaded  (window={cnn_window}, bins={cnn_bins})")
        except Exception as e:
            print(f"  [Models] CNN not loaded ({e}) — using XGBoost only")

        weights = {"alpha": 1.0, "xgb_weight": 1.0, "cnn_weight": 0.0}
        try:
            with open(os.path.join(models_dir, "fusion_weights.json")) as f:
                weights = json.load(f)
            print(f"  [Models] Fusion: alpha={weights['alpha']:.2f} "
                f"(xgb={weights['xgb_weight']:.2f}, cnn={weights['cnn_weight']:.2f})")
        except Exception:
            print("  [Models] No fusion weights — using XGBoost only")

        self.xgb = xgb
        self.cnn = cnn
        self.cnn_mean = cnn_mean
        self.cnn_std = cnn_std
        self.cnn_window = cnn_window
        self.weights = weights

        return xgb, cnn, cnn_mean, cnn_std, cnn_window, weights


    # ─────────────────────────────────────────────────────────────────
    # Inference — called every frame once buffer is full
    # ─────────────────────────────────────────────────────────────────

    def run_inference(self, xgb, cnn, cnn_mean, cnn_std, cnn_window, weights) -> dict | None:
        global _current_prob

        with self._buf_lock:
            if len(self._frame_buf) < self.window_N:
                return None
            w_tab = np.stack(self._frame_buf)         # (window_N, n_cols)
            w_md  = np.stack(self._md_buf) if (cnn is not None and
                                        len(self._md_buf) == self.window_N) else None

        # XGBoost
        x_feat = self.window_features(w_tab).reshape(1, -1)
        p_xgb  = float(xgb.predict_proba(x_feat)[0, 1])

        # CNN
        p_cnn = p_xgb   # fallback: if no CNN, fusion = xgb only
        if cnn is not None and w_md is not None:
            try:
                import torch
                w_norm = (w_md.astype(np.float32) - cnn_mean) / (cnn_std + 1e-6)
                with torch.no_grad():
                    logit = cnn(torch.tensor(w_norm).unsqueeze(0)).item()
                p_cnn = float(1 / (1 + math.exp(-logit)))
            except Exception:
                p_cnn = p_xgb

        alpha   = weights.get("alpha", 1.0)
        p_fused = alpha * p_xgb + (1 - alpha) * p_cnn

        with self._buf_lock:
            _current_prob = p_fused

        return {"p_xgb": round(p_xgb, 3),
                "p_cnn": round(p_cnn, 3),
                "p_fused": round(p_fused, 3)}


    # ─────────────────────────────────────────────────────────────────
    # SSE push — notify all connected phone browsers instantly
    # ─────────────────────────────────────────────────────────────────

    def push_event(self, event_type: str, data: dict):
        msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        with self._sse_lock:
            dead = []
            for client in self._sse_clients:
                try:
                    client["wfile"].write(msg.encode())
                    client["wfile"].flush()
                except Exception:
                    dead.append(client)
            for d in dead:
                self._sse_clients.remove(d)


    def _beep(self, freq: int, ms: int):
        try:
            import winsound
            winsound.Beep(freq, ms)
        except Exception:
            print("\a", end="", flush=True)
