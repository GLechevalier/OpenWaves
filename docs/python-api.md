# Python API

`pip install -e software/pyopenwaves` gives you the `openwaves` package. Core
dependencies are just `numpy` + `pyserial`; extras: `[viz]` (rerun,
matplotlib), `[ble]` (bleak), `[ml]` (sklearn, xgboost, pandas, joblib),
`[dev]` (pytest, ruff).

## The `Radar` facade

```python
from openwaves import Radar

with Radar() as radar:
    radar.configure("cfg/Tracking_MidBw.cfg")   # path, RadarConfig, or list of lines
    radar.start()
    for frame in radar.frames():
        ...
```

What it does for you:

- **Port autodetection** — finds the XDS110 CLI/data pair on Windows and
  Linux (`openwaves.transport.find_radar_ports`; several boards are told
  apart by USB serial number: `Radar(ports=find_radar_ports(serial_number="..."))`).
- **Firmware layout detection** — probes `version` to learn whether TLVs
  stream on the auxiliary data port (TI Motion-and-Presence demo, 1.25 Mbaud
  with a 921600 fallback) or on the CLI port itself (the in-repo
  material-classification firmware). Override with `Radar(layout="single")`
  / `"dual"`.
- **Config quirks** — `%` comments skipped, `baudRate` lines switch the host
  port after acknowledgement, characters are paced 1 ms apart at 1.25 Mbaud
  (the firmware drops back-to-back characters at that rate), `sensorStart`
  is held back until you call `start()`.
- **Recovery** — `radar.warm_reset()` reboots the sensor and re-opens the
  re-enumerated ports; `radar.stop()` / context exit send `sensorStop`.
- **Raw commands** — `radar.send_command("rangeSelCfg 0.1 5.0")` for
  anything the typed layer doesn't cover.

## `FrameData`

Every frame the firmware emits parses into a typed
`openwaves.frames.FrameData`:

| Field | Type | Content |
|---|---|---|
| `frame_number`, `timestamp` | int, float | header frame counter, host receive time |
| `points` | `(N, 7) ndarray` | `x, y, z, doppler, snr, noise, track_index` (m, m/s, dB; index 255 = unassociated) |
| `num_points` | int | valid rows in `points` |
| `tracks` | `list[Track]` | tracker output: id, position, velocity, acceleration, confidence |
| `track_indexes` | ndarray | per-point track association (previous frame) |
| `capon_heatmap` | `(10, 32, 16) float32` | OpenWaves capon 3D beamforming spectrum (TLV 601) |
| `range_profile_major/minor` | ndarray | per-range-bin magnitudes |
| `micro_doppler`, `micro_doppler_features` | ndarray, list | µDoppler spectrum per target + extracted features |
| `presence`, `classifier_probabilities`, `stats` | — | presence zones, classifier output, timing/power/temps |
| `raw_tlvs` | `dict[int, bytes]` | payloads of TLV types nothing parsed |
| `errors` | `list[str]` | non-fatal parse problems (a bad TLV never kills the stream) |

Migrating code written against TI's `parseFrame` dict?
`openwaves.compat.frame_to_output_dict(frame)` produces the old
`outputDict` layout (`pointCloud`, `numDetectedPoints`, `trackData`, ...).

## Custom TLV types

The parser is a registry — extend it without forking:

```python
from openwaves.tlv import DEFAULT_REGISTRY

def parse_my_tlv(payload: bytes, frame):
    frame.extras["my_value"] = int.from_bytes(payload[:4], "little")

DEFAULT_REGISTRY.register(602, parse_my_tlv, name="myCustomTlv")
```

Any TLV type your firmware emits beyond the registered set is preserved in
`frame.raw_tlvs[type_id]`, so nothing is silently dropped. This is exactly
how the OpenWaves firmware's capon heatmap (type 601) is wired in — see
`openwaves/tlv/registry.py`.

`openwaves.tlv.encode` builds byte-exact frames (the mirror of the parser)
— useful for tests and simulators.

## Configurations as objects

```python
from openwaves.config import parse_cfg, RadarConfig, FrameCfg, GuiMonitor, SensorStart, BaudRate

config = parse_cfg("cfg/Tracking_MidBw.cfg")     # lossless round-trip
config.get(FrameCfg).frame_periodicity = 50      # 20 FPS
config.save("cfg/my_variant.cfg")

# or build from scratch
config = RadarConfig(commands=[
    GuiMonitor(point_cloud=2, tracker_info=1),
    BaudRate(baudrate=1250000),
    SensorStart(),
])
radar.configure(config)
```

Commands the models don't cover (and firmware-specific extras like
`trackingCfg`) are preserved verbatim as `RawCommand` — see the
[CLI command reference](cli-commands.md) for what each one means.
Two ready-made profiles ship in the package:
`openwaves.config.get_profile_cfg("mpd_tracking_midbw")` and
`get_profile_cfg("material_classification_default")`.

## Recording and replay

```python
from openwaves.io import RawUartRecorder, FrameRecorder, replay_raw

# raw bytes (parser test fixtures, exact replay)
with RawUartRecorder("capture.bin") as rec, Radar() as radar:
    radar.configure(cfg); radar.start()
    stream = radar._data_stream()
    from openwaves.tlv import sync_and_read_frame
    for _ in range(100):
        rec.write(sync_and_read_frame(stream))

for frame in replay_raw("capture.bin"):          # no hardware needed
    ...

# parsed frames as JSON lines (same layout as software/data sessions)
with FrameRecorder("session.jsonl", metadata={"subject": "S01"}) as rec:
    for frame in radar.frames(count=1200):
        rec.write(frame)
```

The `openwaves record` / `openwaves replay` CLI commands wrap these.

## Flashing

```python
from openwaves import flash_firmware
flash_firmware()          # bundled firmware, guided SOP flow
```

See the [flashing guide](flashing.md).

## BLE (RadarWall ESP32 bridge)

The material-classification hardware streams heatmaps via an ESP32 over
BLE. With the `[ble]` extra:

```python
import asyncio
from openwaves.ble import RadarWallBLEClient, HEATMAP_SHAPE

def on_frame(heatmap, frame_number, timestamp_ms):
    print(frame_number, heatmap.reshape(HEATMAP_SHAPE).max())

async def main():
    client = RadarWallBLEClient(on_frame_complete=on_frame)
    if await client.connect():           # scans for "RadarWall"
        await client.start_recording()
        await asyncio.sleep(30)
        await client.disconnect()

asyncio.run(main())
```

The chunked transfer protocol (16-byte frame headers, 12-byte chunk
headers, RESEND-based retransmission) is handled internally.

## Command line

```
openwaves ports | flash | config | stream | record | replay | term | reset
```

`openwaves term` gives an interactive mmWave CLI prompt — type `help` to
list what the flashed firmware supports.

## Exceptions

All errors derive from `openwaves.OpenWavesError`:
`PortNotFoundError`, `CliTimeoutError`, `CliCommandError` (the firmware
answered `Error`), `FrameSyncError` (no magic word in the stream),
`FlashError` (bootloader NACK, with the device status code).
