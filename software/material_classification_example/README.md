# Material classification

Identify what a wall is made of — without touching it. The radar emits FMCW chirps, and the reflected electromagnetic fingerprint (per-range, per-angle density spectrum) is enough for a neural network to tell wood from aluminium, stone, plastic, plexiglass and layered combinations. Full write-up: [gauthier-lechevalier.com/radar](https://gauthier-lechevalier.com/radar).

## How it works

1. **Chirp & mix** — the radar (TI IWRL6432BOOST + ESP32) emits linear FMCW chirps; the echo is mixed down to beat tones proportional to range.
2. **Range FFT + Capon beamforming (MVDR)** — reflected energy is resolved per depth and per angle across the MIMO RX array, producing a 3D heatmap: the material's electromagnetic fingerprint.
3. **Stream & visualize** — heatmaps stream over BLE to `visualizer/src/rerun/`, replayed live in [Rerun](https://rerun.io).
4. **Classify** — a PyTorch network in `ML/src/` ingests the spectra: **98.8% test accuracy** across 9 multilayer material classes ([results](ML/outputs_materials/outputs_multilayer/results.txt)).

## Layout

- `visualizer/src/rerun/` — BLE client, live Rerun visualization, `.rrd` → `.npy` conversion, clustering
- `visualizer/src/capon_beamforming_visualizer/` — Capon beamforming heatmap visualization
- `ML/src/` — training scripts, models (CNN, ConvNeXt, Astroformer) and data augmentation
- `ML/outputs_materials/` — trained weights, scalers, confusion matrices and results

Recorded captures live in [`../data/rerun_recorded_data/`](../data/rerun_recorded_data/), so everything runs without a radar on your desk.

## Run it

```
python classify_materials.py                        # replay + classify the shipped captures (no radar)
python visualizer/src/rerun/recorded_data_viz.py    # replay a recording in Rerun
python visualizer/src/rerun/data_visualizer.py      # live from the radar over BLE
```

`classify_materials.py` opens a recording in Rerun and shows the shipped
plastic/stone/wood captures are separable from their heatmaps alone (~96%
with a logistic regression trained on half the frames — no GPU, no radar).
The bundled PyTorch weights in `ML/outputs_materials/` are calibrated to
their own recording campaign; record your own captures and retrain
(`ML/src/`) to classify your walls.
