# Getting started

From zero to radar frames in Python. You need: a
[TI IWRL6432BOOST](https://www.ti.com/tool/IWRL6432BOOST) board, a micro-USB
cable, and Python 3.10+ (3.12 recommended).

## 1. Clone and install

```bash
git clone https://github.com/GLechevalier/OpenWaves
cd OpenWaves
python -m venv .venv
.venv\Scripts\activate            # Windows   (source .venv/bin/activate on Linux/macOS)
pip install -e software/pyopenwaves[viz,ble]
```

Using VSCode? Open the repo folder and press **Ctrl+Shift+B** — the default
build task runs the install for you (and `.vscode/` ships tasks for
flashing, streaming and recording).

## 2. Plug the board in

Connect the micro-USB on the board's **XDS110** port. It enumerates two
serial ports (CLI + data). Check that the board is found:

```bash
openwaves ports
```

```
Serial ports:
  COM11        XDS110 Class Application/User UART (COM11)  <-- radar CLI port
  COM12        XDS110 Class Auxiliary Data Port (COM12)    <-- radar DATA port

Detected radars:
  CLI=COM11 DATA=COM12 (S/N L4100xxx)
```

On Linux the ports are typically `/dev/ttyACM0`/`ttyACM1`; add yourself to
the `dialout` group if you get permission errors (see
[troubleshooting](troubleshooting.md)).

## 3. Flash firmware (first time only)

A factory-fresh board runs TI's out-of-box demo. To flash either the
OpenWaves material-classification firmware (bundled with the package) or any
other `.appimage`, follow the [flashing guide](iwrl6432-doc.md/flashing.md) — short version:

```bash
openwaves flash            # bundled firmware; the command walks you through the SOP switches
```

If your board already runs TI's **Motion and Presence Detection** demo, the
fall-detection configs work with it as-is — no reflash needed.

## 4. First frames

```bash
openwaves stream --cfg software/fall_detection_example/cfg/Tracking_MidBw.cfg
```

or in Python:

```python
from openwaves import Radar

with Radar() as radar:                                  # autodetects the ports
    radar.configure("software/fall_detection_example/cfg/Tracking_MidBw.cfg")
    radar.start()
    for frame in radar.frames(count=100):
        print(frame.frame_number, frame.num_points)
        if frame.points is not None:
            xyz = frame.points[:frame.num_points, :3]   # positions in meters
```

`frame` is a typed [`FrameData`](python-api.md#framedata) — point cloud,
tracks, heatmaps, stats, plus raw payloads for anything the parser doesn't
know.

## 5. No hardware? Replay recorded data

Every demo runs from the recordings in `software/data/`. Raw UART captures
replay through the same parser as live data:

```bash
openwaves record capture.bin --raw --duration 10 --cfg <cfg>   # with hardware
openwaves replay capture.bin                                    # without
```

## Where next

- [Python API](python-api.md) — the full package tour.
- [CLI command reference](cli-commands.md) — what every `.cfg` line means.
- Fall detection demo: `software/fall_detection_example/` — run
  `python src/examples/fall_detector_example.py` from that directory.
- Material classification demo: `software/material_classification_example/`.
