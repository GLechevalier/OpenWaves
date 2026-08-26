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

## Quick try — no hardware needed

Three things to run in your first five minutes, straight from a fresh clone:

```
pip install -e software/pyopenwaves[viz,ml] scipy
```

**1. See the antenna simulation results.** Replays the shipped openEMS
results (what the 3 RX antennas receive when a chirp hits a wall) through
the full receive chain — LNA, mixer, ADC, range FFT, Capon beamforming —
and opens the range profile and 3D heatmap plots. No openEMS install needed.

```
cd hardware/electronics/electromagnetic_simulation && python quick_look.py
```

**2. Replay real radar data and classify materials.** Opens a bundled
capture in the [Rerun](https://rerun.io) viewer and shows that the
electromagnetic fingerprints of a plastic sheet, a stone wall and a wood
plank are distinct enough to classify at ~96% from the heatmaps alone.

```
cd software/material_classification_example && python classify_materials.py
```

**3. Write your first radar program — against a virtual radar.** The
`VirtualRadar` synthesizes a scene, encodes it to real firmware wire bytes
and feeds it through the same parser a live board uses, so your code works
unchanged on hardware later. Start from the example (a person walking past
the radar) and make it yours:

```
python software/pyopenwaves/examples/virtual_radar_walk.py --rerun
```

## Get the openwaves devkit

Want to run the demos on real hardware without hunting down parts? **The OpenWaves DIY kit is available [here](https://2t1rza-p3.myshopify.com/products/openwaves-diy-kit-mmwave-radar-development-kit)** — every component in one box: radar board, electronics, battery and casing, ready to assemble yourself following the [docs](docs/README.md). Building your own radar is the best way to understand it — and buying a kit is the best way to support the development of this project.

Prefer to source everything yourself? The repo has you covered: the full [bill of materials](hardware/BOM.md), antenna design, firmware and printable casing live in [hardware/](hardware/).

https://github.com/user-attachments/assets/6c5402e7-b6d7-4883-ae2d-70329f7b1580


## Setup

```
pip install -e software/pyopenwaves[viz,ble]
```

Then plug the board in and check it's found:

```
openwaves ports     # list COM ports, mark the radar
openwaves flash     # flash the prebuilt firmware (guided, USB only)
```

In VSCode, **Ctrl+Shift+B** installs everything and `.vscode/` ships one-click
tasks for flashing, streaming and recording. Full walkthrough:
[docs/getting-started.md](docs/getting-started.md).

`pip install -r requirements.txt` additionally pulls the ML and simulation
dependencies for the demos. For the electromagnetic simulations, also
install openEMS & CSXCAD: download the [openEMS release](https://github.com/thliebig/openEMS-Project/releases), unzip it to your `user/opt` dir, then `pip install` the `csxcad` and `openems` wheels from its `python/` folder — full tutorial [here](https://docs.openems.de/python/install.html).

## Documentation

Comprehensive documentation is available in the [docs/](docs/README.md) folder — everything you need to go from a boxed IWRL6432BOOST to Python code reading radar frames:

- [Getting Started Guide](docs/getting-started.md) — clone, install, plug in, first frames in ~10 lines of Python
- [Python API Reference](docs/python-api.md) & [Radar CLI Commands](docs/cli-commands.md)
- [Radar Physics](docs/physics/README.md) — from semiconductors to FMCW and mmWave concepts
- [IWRL6432 Chip Reference](docs/iwrl6432-doc.md/README.md) — flashing, configuration and TLV format, reverse-engineered
- [Development Handbooks](docs/development-handbooks/README.md) — the lab notebooks: how the radar and the openEMS simulation were built
- [Troubleshooting](docs/troubleshooting.md)

## Processing Pipeline

From chirp to classified target, every frame goes through this chain — the first stages run on the IWRL6432 itself, the rest on the host:

1. **Waveform Generation** — the IWRL6432's on-chip synthesizer ramps 60 GHz FMCW chirps (chirp and frame timing configured from Python)
2. **TX / RX & Down-Conversion** — the echo is mixed with the outgoing chirp (dechirped) to a low-frequency beat signal and digitized by the on-chip ADC
3. **Signal Processing** (on-chip firmware):
   - Raw ADC data capture
   - Range FFT
   - Doppler FFT
   - CFAR detection → point cloud (fall-detection firmware)
   - Capon 3D beamforming heatmaps — the custom OpenWaves DPU (material-classification firmware)
4. **Streaming** — results packed as TLV frames over USB UART, or over BLE via the ESP32 bridge
5. **Host Processing & Visualization** (Python) — `pyopenwaves` parses the TLV stream into typed frames, [Rerun](https://rerun.io) renders them live, and PyTorch models sit on top

The same chain is **implemented in simulation**: openEMS computes the fields at the RX antennas, and the receive chain — LNA, mixer, ADC, range FFT, Capon beamforming — is replayed in Python (`quick_look.py`), while `VirtualRadar` synthesizes scenes and encodes them into real firmware wire bytes. Every stage can be traced end to end without hardware on your desk.

The two demos each exercise one branch of stage 3: **material classification** takes the Capon heatmap path (on-chip 3D heatmaps → BLE → Rerun → PyTorch, ~96% on plastic/stone/wood), and **fall detection** takes the point-cloud path (CFAR detections + tracking → CNN fall classifier).

<!-- Rerun session video of the radar outputs — drop the recording below -->

## License

Different parts of this repo are under different terms:

- **Software and hardware designs authored by this project** — the `openwaves` Python package, the demos, the ESP32 firmware, the antenna and casing designs, and the docs — are licensed under the [GNU General Public License v3.0](LICENSE).
- **The radar firmware in [`hardware/firmware/IWRL6432BOOST_firmware/`](hardware/firmware/IWRL6432BOOST_firmware/) is a derivative of TI's mmWave SDK demo** and remains governed by Texas Instruments' license terms (the original TI copyright headers are kept in the source files). It is **not** covered by the GPL. The same applies to the prebuilt `.appimage` shipped in the Python package, which is built against TI's MMWAVE-L-SDK.
- The TI IWRL6432 silicon and the IWRL6432BOOST board design are TI's proprietary products and are not part of this repository.
