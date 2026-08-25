# src/data_processors/PostureDetector.py

import numpy as np
import rerun as rr
import joblib
import os
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


class PostureDetector:
    """
    SVM-based posture detector (standing / sitting / lying).

    Features used:
        - z_mean    : mean height of point cloud (floor-relative)
        - z_extent  : vertical spread (max_z - min_z)
        - xy_spread : std of points in the horizontal plane
        - flatness  : λ2 / λ0  (0 = needle, 1 = sphere/pancake)

    Two modes:
        - COLLECT : call collect_sample(point_cloud_list, label) to build a dataset
        - PREDICT : call update(point_cloud_list) to classify in real time

    Workflow:
        detector = PostureDetector(radar_height=1.5)
        # --- collection phase ---
        detector.collect_sample(pc_list, "standing")
        detector.collect_sample(pc_list, "lying")
        ...
        detector.train_and_save("models/posture_svm.pkl")
        # --- inference phase ---
        detector.load("models/posture_svm.pkl")
        label = detector.update(pc_list)
    """

    LABELS     = ["standing", "sitting", "lying"]
    MIN_POINTS = 8
    SMOOTH_K   = 7

    _LABEL_TO_INT = {"standing": 0, "sitting": 1, "lying": 2, "unknown": 3}
    _COLORS = {
        "standing": [0,   220, 120, 255],
        "sitting":  [255, 180,   0, 255],
        "lying":    [80,  160, 255, 255],
        "unknown":  [160, 160, 160, 255],
    }

    def __init__(self, radar_height: float = 1.5, smooth_k: int = 7,
                 model_path: str = None):
        """
        Parameters
        ----------
        radar_height : float
            Radar mounting height above the floor in meters.
        smooth_k : int
            Majority-vote smoothing window (frames).
        model_path : str, optional
            Path to a pre-saved .pkl model to load immediately.
        """
        self._radar_height = radar_height
        self.SMOOTH_K      = smooth_k
        self._history      = []

        # SVM pipeline (scaler + classifier)
        self._pipeline: Pipeline = None

        # Dataset buffers for collection mode
        self._X: list = []   # feature vectors
        self._y: list = []   # string labels

        if model_path and os.path.exists(model_path):
            self.load(model_path)

    # ── Public: inference ─────────────────────────────────────────────

    def update(self, point_cloud_list: list) -> str:
        """
        Classify current posture from sliding-window point cloud list.
        Returns smoothed label: 'standing' | 'sitting' | 'lying' | 'unknown'
        """
        pts = self._collect_points(point_cloud_list)
        if pts is None:
            return self._log("unknown", None)

        features = self._extract_features(pts)

        if self._pipeline is None:
            print("[PostureDetector] No model loaded — call train_and_save() first.")
            return self._log("unknown", features)

        vec   = self._to_vector(features)
        label = self._pipeline.predict([vec])[0]
        label = self._smooth(label)
        return self._log(label, features)

    # ── Public: data collection ───────────────────────────────────────

    def collect_sample(self, point_cloud_list: list, label: str):
        """
        Add one labeled sample to the training buffer.

        Parameters
        ----------
        label : str
            One of 'standing', 'sitting', 'lying'
        """
        assert label in self.LABELS, f"label must be one of {self.LABELS}"
        pts = self._collect_points(point_cloud_list)
        if pts is None:
            print(f"[PostureDetector] Skipped sample '{label}': not enough points.")
            return

        features = self._extract_features(pts)
        self._X.append(self._to_vector(features))
        self._y.append(label)
        counts = {l: self._y.count(l) for l in self.LABELS}
        print(f"[PostureDetector] Sample added '{label}' | buffer: {counts}")

    def train_and_save(self, save_path: str = "models/posture_svm.pkl"):
        """
        Train an SVM on collected samples and save the pipeline.
        Requires at least 2 classes and 5 samples per class.
        """
        X = np.array(self._X)
        y = np.array(self._y)

        classes, counts = np.unique(y, return_counts=True)
        print(f"[PostureDetector] Training on {len(y)} samples: "
              f"{dict(zip(classes, counts))}")

        if len(classes) < 2:
            print("[PostureDetector] Need at least 2 classes to train.")
            return
        if counts.min() < 5:
            print("[PostureDetector] Need at least 5 samples per class.")
            return

        self._pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("svm",    SVC(kernel="rbf", C=10, gamma="scale",
                           class_weight="balanced", probability=True)),
        ])
        self._pipeline.fit(X, y)

        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        joblib.dump(self._pipeline, save_path)
        print(f"[PostureDetector] Model saved → {save_path}")

        # Quick cross-val score
        from sklearn.model_selection import cross_val_score
        scores = cross_val_score(self._pipeline, X, y, cv=min(5, counts.min()))
        print(f"[PostureDetector] CV accuracy: {scores.mean():.2%} ± {scores.std():.2%}")

    def load(self, path: str):
        """Load a previously saved model pipeline."""
        self._pipeline = joblib.load(path)
        print(f"[PostureDetector] Model loaded ← {path}")

    def clear_buffer(self):
        """Reset the data collection buffer."""
        self._X, self._y = [], []
        print("[PostureDetector] Buffer cleared.")

    # ── Feature extraction ────────────────────────────────────────────

    def _collect_points(self, point_cloud_list):
        if not point_cloud_list:
            return None
        valid = [pc[:, :3] for pc in point_cloud_list
                 if pc is not None and len(pc) > 0]
        if not valid:
            return None
        pts = np.vstack(valid)
        return pts if len(pts) >= self.MIN_POINTS else None

    def _extract_features(self, pts: np.ndarray) -> dict:
        # Floor-relative Z
        pts = pts.copy()
        pts[:, 2] = self._radar_height - pts[:, 2]

        # ── Basic stats ───────────────────────────────────────────────
        z_mean   = float(pts[:, 2].mean())
        z_extent = float(pts[:, 2].max() - pts[:, 2].min())
        xy_spread = float(pts[:, :2].std())

        # ── PCA for flatness ──────────────────────────────────────────
        centered = pts - pts.mean(axis=0)
        cov = np.cov(centered.T)
        eigenvalues = np.linalg.eigvalsh(cov)   # ascending
        eigenvalues = eigenvalues[::-1]          # descending: λ0 ≥ λ1 ≥ λ2
        lam0, _, lam2 = eigenvalues
        flatness = float(lam2 / (lam0 + 1e-6))  # 0 = needle, ~1 = pancake

        return dict(
            pts=pts,
            z_mean=z_mean,
            z_extent=z_extent,
            xy_spread=xy_spread,
            flatness=flatness,
        )

    @staticmethod
    def _to_vector(f: dict) -> list:
        """Ordered feature vector fed to the SVM."""
        return [f["z_mean"], f["z_extent"], f["xy_spread"], f["flatness"]]

    # ── Smoothing ─────────────────────────────────────────────────────

    def _smooth(self, label: str) -> str:
        self._history.append(label)
        if len(self._history) > self.SMOOTH_K:
            self._history.pop(0)
        return max(set(self._history), key=self._history.count)

    # ── Rerun logging ─────────────────────────────────────────────────

    def _log(self, label: str, f: dict) -> str:
        color = self._COLORS[label]
        rr.log("posture/label",  rr.Scalars(self._LABEL_TO_INT[label]))
        rr.log("posture/status", rr.TextLog(
            f"POSTURE → {label.upper()}",
            level=rr.TextLogLevel.INFO,
        ))
        if f:
            rr.log("posture/features/z_mean",   rr.Scalars(f["z_mean"]))
            rr.log("posture/features/z_extent",  rr.Scalars(f["z_extent"]))
            rr.log("posture/features/xy_spread", rr.Scalars(f["xy_spread"]))
            rr.log("posture/features/flatness",  rr.Scalars(f["flatness"]))

            pts = f["pts"]
            mins, maxs = pts.min(axis=0), pts.max(axis=0)
            rr.log("radar/posture_bbox", rr.Boxes3D(
                centers=[(mins + maxs) / 2],
                half_sizes=[(maxs - mins) / 2],
                colors=[(*color[:3], 80)],
            ))
        return label