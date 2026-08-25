# OpenWaves docs

Everything you need to go from a boxed IWRL6432BOOST to Python code reading
radar frames.

## Getting started

- [Getting started](getting-started.md) — clone, install, plug in, first frames in ~10 lines of Python.
- [Flashing firmware](flashing.md) — one-command USB flashing, SOP switch guide, no TI software needed.
- [Troubleshooting](troubleshooting.md) — ports, baud rates, sync issues, flash errors.

## The Python package (`openwaves`)

- [Python API](python-api.md) — the `Radar` facade, `FrameData`, custom TLV types, recording & replay, BLE, flashing from Python.
- [Radar CLI command reference](cli-commands.md) — every firmware CLI command, adapted to the Python API.
- [TLV output format](tlv-format.md) — the UART frame format the radar streams, byte by byte.
- [mmWave concepts](mmwave-concepts.md) — FMCW basics mapped to the config parameters you'll actually set.

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
