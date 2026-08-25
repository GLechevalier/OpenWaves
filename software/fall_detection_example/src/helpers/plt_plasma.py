import numpy as np

# ── Plasma colormap helper (no matplotlib needed) ────────────────────────────
def plt_plasma(t: np.ndarray) -> np.ndarray:
    """Map values in [0,1] to plasma RGBA using a simple lookup."""
    plasma_pts = np.array([
        [13,  8,  135], [70,  3,  159], [114,  1,  168],
        [156, 23,  158], [189, 55,  134], [216, 87,  107],
        [237, 121,  83], [251, 159,  58], [253, 202,  38], [240, 249,  33],
    ], dtype=np.float32)
    t = np.clip(t, 0, 1)
    idx = t * (len(plasma_pts) - 1)
    lo  = idx.astype(int)
    hi  = np.clip(lo + 1, 0, len(plasma_pts) - 1)
    frac = (idx - lo)[:, None]
    rgb = plasma_pts[lo] * (1 - frac) + plasma_pts[hi] * frac
    alpha = np.full((len(t), 1), 200, dtype=np.float32)
    return np.concatenate([rgb, alpha], axis=1).astype(np.uint8)