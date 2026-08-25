import numpy as np

# --- Color helper ---
def doppler_to_color(doppler):
    if len(doppler) == 0:
        return np.empty((0, 3), dtype=np.uint8)
    max_val = max(np.abs(doppler).max(), 1e-6)
    norm = np.clip(doppler / max_val, -1, 1)
    colors = np.zeros((len(doppler), 3), dtype=np.uint8)
    colors[:, 0] = np.clip(norm * 255, 0, 255).astype(np.uint8)   # Red = receding
    colors[:, 2] = np.clip(-norm * 255, 0, 255).astype(np.uint8)  # Blue = approaching
    return colors
