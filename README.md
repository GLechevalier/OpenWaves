# OpenWaves — open-source 60 GHz mmWave radar platform built on the TI IWRL6432

![OpenWaves radar](public/images/Radar.png)

[docs](docs/README.md) · [python package](software/pyopenwaves/) · [material classification](software/material_classification_example/) · [fall detection](software/fall_detection_example/) · [hardware](hardware/)

Everything you need to get started with mmWave radar: an electromagnetic simulation you can play with, a custom antenna, electronics and printable casing, and the software to run two end-to-end demos: material classification and fall detection.

The radar transceiver itself is **not** an open design: it is Texas Instruments' IWRL6432 FMCW SoC, used on TI's [IWRL6432BOOST](https://www.ti.com/tool/IWRL6432BOOST) evaluation board. What this repo open-sources is everything *around* that chip — the result of 4 months of reverse engineering the IWRL6432BOOST on two fronts: its **antenna array**, re-created as a 3D model and validated in openEMS electromagnetic simulations, and its **interface layer** (flashing protocol, configuration CLI, TLV data format, documented in [docs/iwrl6432-doc.md/](docs/iwrl6432-doc.md/)), so the board can be driven entirely from Python with zero TI software installed.

This repo is the open-source release of the radar behind [*I built a mmWave material classification radar*](https://gauthier-lechevalier.com/radar), [discussed on this Hacker News post](https://news.ycombinator.com/item?id=48736137).

*OpenWaves is an independent project. It is not affiliated with, sponsored by, or endorsed by Texas Instruments. "Texas Instruments", "IWRL6432" and "IWRL6432BOOST" are used only to identify the off-the-shelf hardware the project runs on.*

## Features

- **Electromagnetic simulation** — antenna, emission and reflection sims built on [openEMS](https://www.openems.de). `hardware/electronics/electromagnetic_simulation/`
- **`openwaves` Python package** — plug the radar in via USB and drive everything from Python: flash firmware (`openwaves flash`, no TI software needed), send configurations, stream typed point-cloud/heatmap frames. `software/pyopenwaves/`
- **Material classification** — Capon 3D beamforming heatmaps streamed over BLE from the radar, visualized live in [Rerun](https://rerun.io), and classified with a PyTorch neural network. `software/material_classification_example/`
- **Fall detection** — real-time point-cloud tracking on a TI IWRL6432BOOST, with a CNN fall classifier and dual-radar room visualization. `software/fall_detection_example/`
- **Hardware included** — antenna 3D model (PCB fab files coming), firmware, and a 3D-printable casing. `hardware/`
- **Recorded data** — `.rrd` / `.npy` radar captures in `software/data/`, so every demo runs without a radar on your desk.

## Getting started

```
pip install -e software/pyopenwaves[viz,ble,ml] scipy
```

**No hardware needed** — three things to try from a fresh clone:

**1. Antenna simulation replay** — the shipped openEMS results through the full receive chain (LNA → mixer → ADC → range FFT → Capon beamforming), with range profile and 3D heatmap plots. No openEMS install needed.

```
cd hardware/electronics/electromagnetic_simulation && python quick_look.py
```

**2. Classify materials from real data** — a bundled capture in the [Rerun](https://rerun.io) viewer: plastic, stone and wood told apart at ~96% from the heatmaps alone.

```
cd software/material_classification_example && python classify_materials.py
```

**3. Your first radar program** — `VirtualRadar` synthesizes a scene as real firmware wire bytes, so your code runs unchanged on hardware later.

```
python software/pyopenwaves/examples/virtual_radar_walk.py --rerun
```

**Got a board?**

```
openwaves ports     # list COM ports, mark the radar
openwaves flash     # flash the prebuilt firmware (guided, USB only)
```

In VSCode, **Ctrl+Shift+B** installs everything and `.vscode/` ships one-click flash/stream/record tasks. Full walkthrough: [docs/getting-started.md](docs/getting-started.md). To run *new* electromagnetic simulations, install openEMS & CSXCAD ([tutorial](https://docs.openems.de/python/install.html)).

## Get the openwaves devkit

Want to run the demos on real hardware without hunting down parts? **The OpenWaves DIY kit is available [here](https://2t1rza-p3.myshopify.com/products/openwaves-diy-kit-mmwave-radar-development-kit)** — every component in one box: radar board, electronics, battery and casing, ready to assemble yourself following the [docs](docs/README.md). Building your own radar is the best way to understand it — and buying a kit is the best way to support the development of this project.

Prefer to source everything yourself? The repo has you covered: the full [bill of materials](hardware/BOM.md), antenna design, firmware and printable casing live in [hardware/](hardware/).

https://github.com/user-attachments/assets/6c5402e7-b6d7-4883-ae2d-70329f7b1580


## Documentation

Comprehensive documentation is available in the [docs/](docs/README.md) folder — everything you need to go from a boxed IWRL6432BOOST to Python code reading radar frames:

- [Getting Started Guide](docs/getting-started.md) — clone, install, plug in, first frames in ~10 lines of Python
- [Python API Reference](docs/python-api.md) & [Radar CLI Commands](docs/cli-commands.md)
- [Radar Physics](docs/physics/README.md) — from semiconductors to FMCW and mmWave concepts
- [IWRL6432 Chip Reference](docs/iwrl6432-doc.md/README.md) — flashing, configuration and TLV format, reverse-engineered
- [Development Handbooks](docs/development-handbooks/README.md) — the lab notebooks: how the radar and the openEMS simulation were built
- [Troubleshooting](docs/troubleshooting.md)

## Processing Pipeline

From chirp to classified target — the first stages run on the IWRL6432, the rest on the host:

1. **Chirp Generation** — on-chip synthesizer ramps 60 GHz FMCW chirps, configured from Python
2. **RX & Down-Conversion** — echoes dechirped to a beat signal, digitized on-chip
3. **Signal Processing** (on-chip) — range FFT, Doppler FFT, then CFAR → point cloud, or Capon 3D heatmaps (custom OpenWaves DPU)
4. **Streaming** — TLV frames over USB UART, or BLE via the ESP32 bridge
5. **Host** (Python) — `pyopenwaves` parses, [Rerun](https://rerun.io) visualizes, PyTorch classifies

The same chain is **implemented in simulation** — openEMS antenna fields replayed through LNA → mixer → ADC → range FFT → Capon in `quick_look.py` — so every stage runs without hardware. Each demo exercises one stage-3 branch: **material classification** the Capon heatmaps (~96% on plastic/stone/wood), **fall detection** the CFAR point cloud (tracking → CNN).

https://github.com/user-attachments/assets/32a75c31-3abb-4321-8420-30cb97ea54ee

## License

Different parts of this repo are under different terms:

- **Software and hardware designs authored by this project** — the `openwaves` Python package, the demos, the ESP32 firmware, the antenna and casing designs, and the docs — are licensed under the [GNU General Public License v3.0](LICENSE).
- **The radar firmware in [`hardware/firmware/IWRL6432BOOST_firmware/`](hardware/firmware/IWRL6432BOOST_firmware/) is a derivative of TI's mmWave SDK demo** and remains governed by Texas Instruments' license terms (the original TI copyright headers are kept in the source files). It is **not** covered by the GPL. The same applies to the prebuilt `.appimage` shipped in the Python package, which is built against TI's MMWAVE-L-SDK.
- The TI IWRL6432 silicon and the IWRL6432BOOST board design are TI's proprietary products and are not part of this repository.
