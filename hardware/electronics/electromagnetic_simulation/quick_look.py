"""Quick look at the antenna simulation results — no openEMS install needed.

Replays the shipped openEMS reflection results (saved/rx_signal_plus.npy /
rx_signal_moins.npy: what the 3 RX antennas receive when TX1±TX2 emit one
FMCW chirp at a wall 1.5 cm away) through the full receive chain:

    LNA -> mixer -> IF low-pass -> ADC  →  BPM decode → range FFT → Capon 3D

Two matplotlib windows open: the range profiles per virtual antenna, and the
Capon beamforming heatmap with a range-bin slider. Rerunning the actual
electromagnetic simulation (antenna S11, directivity, new scenes) needs
openEMS — see the README; the resulting plots are in
public/images/simulation/.

Run from this directory:  python quick_look.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from src.emission_sim import ChirpGenerator
from src.reflection_sim import RXSignals, resolve_saved_path
from src.rf_receiver_sim import RFReceiverSim
from src.digital_processing import BPMDecoder, CaponBeamforming, RadarOutputVisualizer, RangeFFT

# The chirp the saved signals were simulated with (see main.py)
CHIRP_PARAMS = dict(
    amplitude=1, offset=0, phase_offset=0,
    frequency_start=58,      # GHz
    frequency_slope=160,     # MHz/us
    TX_start_time=0, ramp_end_time=24.3, idle_time=1,  # us
    number_of_chirps=1, time_step=1e-5, start_time=0.0,
)


def main():
    print("Generating the 58 GHz FMCW TX chirp (2.5M samples, ~10 s)...")
    tx_chirp = ChirpGenerator(**CHIRP_PARAMS)

    print("Loading the saved openEMS RX signals (3 antennas, TX1+TX2 and TX1-TX2)...")
    rx_signals = RXSignals(
        rx_signal_chirp_plus=np.load(resolve_saved_path("saved/rx_signal_plus.npy")),
        rx_signal_chirp_moins=np.load(resolve_saved_path("saved/rx_signal_moins.npy")),
    )

    print("Receive chain: LNA -> mixer -> IF low-pass -> ADC (256 samples @ 12.5 MHz)...")
    receiver = RFReceiverSim(tx_signal=tx_chirp, rx_signals=rx_signals)
    adc = receiver.run()

    print("BPM decoding -> 6 virtual antennas, range FFT, Capon beamforming...")
    adc_data = BPMDecoder().binary_phase_decoding(
        adc_data_plus=adc["plus"], adc_data_moins=adc["moins"]
    )
    range_fft = RangeFFT()
    range_profile = range_fft.range_fft(adc_data=adc_data)

    # range axis: beat frequency → distance (fs after ADC, chirp slope S)
    range_fft.fs = receiver.adc_sample_rate * 1e6            # Hz
    range_fft.S = CHIRP_PARAMS["frequency_slope"] * 1e12     # Hz/s
    ranges = range_fft.get_range_bins()
    peak_bin = int(np.abs(range_profile).sum(axis=0)[: len(ranges) // 2].argmax())
    print(f"Strongest return: bin {peak_bin} ~= {ranges[peak_bin]*100:.1f} cm "
          "(the simulated wall sits at 1.5 cm)")

    heatmap = CaponBeamforming().capon_beamforming(range_profile=range_profile)

    print("Opening plots (close the windows to exit)...")
    range_fft.plot_range_profile(antenna_idx=0)
    RadarOutputVisualizer(max_range_bin=10).visualize_capon_3D_heatmap(capon_3D_heatmap=heatmap)


if __name__ == "__main__":
    main()
