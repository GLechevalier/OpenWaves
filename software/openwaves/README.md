# PyOpenWaves

Python toolkit for the TI IWRL6432BOOST mmWave radar (the board behind
[OpenWaves](https://github.com/GLechevalier/OpenWaves)). Flash firmware,
send configurations, stream and parse TLV frames — **no TI software
required**.

```bash
pip install -e software/openwaves[viz,ble]   # from the OpenWaves repo root
```

```python
from openwaves import Radar

with Radar() as radar:                        # autodetects the XDS110 COM ports
    radar.configure("cfg/Tracking_MidBw.cfg") # or a RadarConfig object
    radar.start()
    for frame in radar.frames(count=10):
        print(frame.frame_number, frame.num_points, frame.points)
```

Command line:

```bash
openwaves ports        # find the board
openwaves flash        # flash the bundled prebuilt firmware (SOP switch guide included)
openwaves stream --cfg cfg/Tracking_MidBw.cfg
openwaves record capture.bin --raw --duration 10
openwaves replay capture.bin
openwaves term         # interactive mmWave CLI
```

Highlights:

- **Self-contained flasher** — a clean-room implementation of the xWRL6432
  UART ROM bootloader (`openwaves.flash`); the prebuilt
  material-classification firmware ships inside the wheel.
- **Typed TLV parser** with an extensible registry (`openwaves.tlv`) —
  point clouds, tracks, range profiles, micro-Doppler, stats, and the
  OpenWaves capon 3D heatmap (TLV 601, shape 10×32×16). Register your own
  TLV types without forking.
- **Config models** (`openwaves.config`) — dataclasses for the mmWave CLI
  commands with lossless `.cfg` round-trip.
- **All the UART quirks handled** — port autodetection, `baudRate`
  switching, char-by-char writes at 1.25 Mbaud, warm-reset recovery.
- **BLE client** for the RadarWall ESP32 bridge (`openwaves.ble`, needs the
  `ble` extra).

Full documentation lives in the repository's [`docs/`](../../docs) folder.

License: GPL-3.0-or-later (note: flashed firmware images embed TI MMWAVE-L-SDK
components under TI's own license).
