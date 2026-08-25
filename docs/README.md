# OpenWaves docs

Everything you need to go from a boxed IWRL6432BOOST to Python code reading
radar frames. The docs are organized in four parts: the guides at this
level, the physics behind the radar, the IWRL6432 chip reference, and the
development handbooks that tell how it was all built.

## Guides (this folder)

Practical, start-here material:

- [Getting started](getting-started.md) — clone, install, plug in, first frames in ~10 lines of Python.
- [Troubleshooting](troubleshooting.md) — ports, baud rates, sync issues, flash errors.
- [Python API](python-api.md) — the `Radar` facade, `FrameData`, custom TLV types, recording & replay, BLE, flashing from Python.
- [Radar CLI command reference](cli-commands.md) — every firmware CLI command, adapted to the Python API.

## [Physics](physics/README.md)

The theory behind the device, from semiconductors to FMCW: how active RF
devices work, why receivers are architected the way they are, how a wall
reflects an electromagnetic wave, and how mmWave concepts map to the
config parameters you'll actually set. Start with
[mmWave concepts](physics/mmwave-concepts.md) if you just want to
configure the radar; read the rest to understand it.

## [IWRL6432 reference](iwrl6432-doc.md/README.md)

Everything specific to the TI IWRL6432 chip and the BOOST board: flashing
over USB, the SDK functions and memory map used by the firmware, the full
chirp/frame/DPC configuration reference with the OpenWaves values, and the
TLV byte format the radar streams.

## [Development handbooks](development-handbooks/README.md)

The condensed lab notebooks: how the radar went from an unboxed eval kit
to a full material-classification chain, and how the openEMS
electromagnetic simulation was built to generate training data, including
the tricks (Gaussian-pulse transfer functions) and the bugs (the TX2
excitation hunt).

## Demos

- Fall detection — `software/fall_detection_example/` (point cloud + tracking on TI's Motion-and-Presence firmware).
- Material classification — `software/material_classification_example/` (capon 3D heatmaps over BLE → Rerun → PyTorch).

## Hardware

- [Firmware](../hardware/firmware/IWRL6432BOOST_firmware/README.md) — the custom capon-beamforming firmware, rebuilding it with CCS.
- [Bill of materials](../hardware/BOM.md), antenna design and printable casing — `hardware/`.

## AI-assisted bench work (nff)

The [nff](https://github.com/GLechevalier/nff) IoT bridge connects Claude
Code (or any MCP client) to the bench: serial monitoring (`nff monitor`),
crash diagnosis (`nff diagnose`), and build/flash for the ESP32 BLE bridge
firmware. The repo ships a VSCode task ("Radar: Serial monitor (nff)");
the IWRL6432 radar itself is flashed with `openwaves flash` (nff's flash
targets Arduino/PlatformIO boards like the ESP32).
