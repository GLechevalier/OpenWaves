# OpenWaves — agent guide

Open-source 60 GHz mmWave radar platform around the TI IWRL6432BOOST: a
Python package (`software/pyopenwaves`, imports as `openwaves`), two ML
demos, an openEMS electromagnetic simulation, and hardware designs.

## Verify the repo works (no hardware, no GUI)

```
pip install -e software/pyopenwaves[viz,ml,dev] scipy
pytest software/pyopenwaves/tests -q          # ~30 tests, seconds, 1 hardware test skips
```

## The three demos (no hardware)

Run these to exercise the repo end-to-end; each opens GUI windows, with a
headless option noted:

1. `cd hardware/electronics/electromagnetic_simulation && python quick_look.py`
   — replays shipped openEMS results through the receive chain (range FFT +
   Capon). Headless: set `MPLBACKEND=Agg`; success = it prints the strongest
   return bin. Recomputing the EM sim itself needs an openEMS install.
2. `cd software/material_classification_example && python classify_materials.py`
   — classifies the three shipped material captures (~96%). Headless: add
   `--no-viewer`; success = per-material accuracy table.
3. `python software/pyopenwaves/examples/virtual_radar_walk.py`
   — a `VirtualRadar` (`openwaves.virtual`) synthesizes frames through the
   real TLV encode→parse path. Terminal output by default; `--rerun` opens
   a viewer. This is the template for writing radar code with no board.

## Needs hardware or extra setup — don't run blind

- `openwaves flash` / `stream` / `ports`, and most of
  `software/fall_detection_example/` need an IWRL6432BOOST on USB.
- Fall-detection deep models need `pip install torch json_fix`; the SPiKE
  pose scripts additionally need a `SPIKE_DIR` workspace (see that README).
- Rerun scripts call `spawn=True` (viewer window); the rerun-sdk is pinned
  to 0.28.x — the shipped `.rrd` captures were recorded with it.

## Layout

- `software/pyopenwaves/` — the package: CLI (`openwaves` or `python -m openwaves`), TLV parser/encoder, flashing, `VirtualRadar`
- `software/data/` — shipped `.rrd`/`.npy` captures the demos replay
- `software/material_classification_example/`, `software/fall_detection_example/` — demos (each has a README)
- `hardware/` — antenna model, firmware (TI-licensed), casing, EM simulation
- `docs/` — getting started, Python API, reverse-engineered chip docs, physics
