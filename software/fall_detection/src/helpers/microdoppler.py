import numpy as np
import rerun as rr

# Ring buffer for micro-doppler waterfall: shape (UDOPPLER_HISTORY, numDopplerBins)
# Keyed per target index
UDOPPLER_HISTORY = 128  # number of frames kept — increase for longer time window
udoppler_waterfall = None  # shape (numDopplerBins, UDOPPLER_HISTORY) — will init on first frame


def log_microdoppler(outputDict, frame_idx):
    global udoppler_waterfall

    udoppler = outputDict.get('microDopplerOutput')  # shape (numTargets, numDopplerBins)
    num_targets = outputDict.get('numTargets', 0)

    if udoppler is None or num_targets == 0:
        return

    num_bins = udoppler.shape[1]

    # Average across targets if multiple — gives one spectrum per frame
    spectrum = np.mean(udoppler.astype(np.float32), axis=0)  # (numDopplerBins,)

    # Convert to dB
    spectrum_db = 20.0 * np.log10(np.maximum(spectrum, 1e-6))

    # Init waterfall buffer on first frame: rows=Doppler bins, cols=time frames
    if udoppler_waterfall is None:
        udoppler_waterfall = np.full((num_bins, UDOPPLER_HISTORY), spectrum_db.min(), dtype=np.float32)

    # Shift left (oldest frame drops off), insert new spectrum on the right
    udoppler_waterfall = np.roll(udoppler_waterfall, shift=-1, axis=1)
    udoppler_waterfall[:, -1] = spectrum_db

    # Flip vertically so positive Doppler is at top (matching the reference image)
    display = np.flipud(udoppler_waterfall)

    rr.log(
        "radar/microdoppler/spectrogram",
        rr.Tensor(display, dim_names=["doppler_freq", "time"])
    )