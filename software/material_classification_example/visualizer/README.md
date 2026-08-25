# Visualizers

- `src/rerun/data_visualizer.py` — live capon 3D heatmaps from the radar
  over BLE (RadarWall ESP32 bridge, `openwaves.ble`) into
  [Rerun](https://rerun.io). Needs `pip install -e software/pyopenwaves[ble,viz]`.
- `src/rerun/recorded_data_viz.py` — replay a recorded `.rrd` capture from
  `../../data/rerun_recorded_data/` without hardware.
- `src/rerun/Converter.py` — convert `.rrd` recordings to `.npy` heatmap
  stacks for training.
- `src/capon_beamforming_visualizer/` — matplotlib slice-by-slice viewer
  over raw capon output.
