# TLV output format

After `sensorStart`, the firmware streams binary frames over UART — on the
auxiliary data port for TI's MPD demo, on the CLI port itself for the
material-classification firmware. `openwaves` parses this for you
(`radar.frames()`), but the format matters when you add firmware TLVs or
debug captures.

## Frame layout

```
┌─────────────────────────────┐
│ Frame header      40 bytes  │  starts with the magic word
├─────────────────────────────┤
│ TLV 0: type,len   8 bytes   │
│ TLV 0: payload    len bytes │
├─────────────────────────────┤
│ ... numTLVs items ...       │
├─────────────────────────────┤
│ zero padding                │  to a multiple of 32 bytes
└─────────────────────────────┘
```

**Frame header** — little-endian, `struct` format `<Q8I`:

| Offset | Field | Notes |
|---|---|---|
| 0 | magic word (8 B) | bytes `02 01 04 03 06 05 08 07` on the wire — scan for this to sync |
| 8 | version | SDK version |
| 12 | totalPacketLen | whole frame, **including** the 32-byte-multiple padding |
| 16 | platform | e.g. 0xA6432 |
| 20 | frameNumber | monotonically increasing |
| 24 | timeCpuCycles | |
| 28 | numDetectedObj | point count this frame |
| 32 | numTLVs | items that follow |
| 36 | subFrameNumber | |

**TLV item header** — `<2I`: `type`, then payload `length` in bytes
(header excluded).

To read a stream: scan byte-wise for the magic word, read the header, then
read `totalPacketLen − 40` more bytes
(`openwaves.tlv.sync_and_read_frame` does exactly this, and
`openwaves.tlv.encode.encode_frame` produces the same format for tests).

## TLV types openwaves parses

| Type | Name | Payload | Lands in `FrameData.` |
|---|---|---|---|
| 1 | detected points | N × 4 float32 (x, y, z, doppler) | `points[:, 0:4]` |
| 7 | side info | N × 2 uint16, 0.1 dB steps (snr, noise) | `points[:, 4:6]` |
| 301 | detected points (compressed) | unit struct (4 float + 2 int16) then N × (4 int16 + 2 uint8) | `points` |
| 2 / 302 / 303 | range profile (legacy / major / minor) | uint32 per range bin | `range_profile[_major/_minor]` |
| 306 | ext stats | 2 uint32 timings + 4 uint16 power (mW) + 4 uint16 temps (°C) | `stats` |
| 308 / 1010 | target list | N × (uint32 id + 27 float: pos, vel, acc, 4×4 EC, g, confidence) | `tracks` |
| 309 / 1011 | target index | uint8 per point (253 weak, 254 out-of-bounds, 255 noise) | `track_indexes`, `points[:, 6]` |
| 310 | µDoppler raw | float32, (numTargets × numDopplerBins) | `micro_doppler` |
| 311 | µDoppler features | 6 float32 per target (fLow, fUp, bwPwr, meanFreq, medFreq, sEntropy) | `micro_doppler_features` |
| 315 | enhanced presence | zone count byte + 2 bits/zone | `presence` |
| 317 | classifier info | int8 probabilities / 128 | `classifier_probabilities` |
| **601** | **capon 3D heatmap (OpenWaves custom)** | **5120 float32 = 10 depth slices × 32 × 16** | `capon_heatmap` |

Anything else lands untouched in `frame.raw_tlvs[type_id]` — nothing is
dropped. See `openwaves/tlv/defines.py` for the full id list from TI's
demos.

## The capon heatmap (type 601)

The in-repo firmware runs a custom Capon (MVDR) beamforming DPU on-chip and
streams the resulting 3D spatial spectrum every frame: shape
`(10, 32, 16)` = (depth slices, height bins, width bins), float32 power
values. This is the input to the material-classification network
(`input_size = 5120`) and to the Rerun visualizer. The same array arrives
over BLE via the RadarWall bridge (`openwaves.ble`).

## Adding your own TLV

1. Firmware: pick an id ≥ 600 that's unused, write the TLV header + payload
   in `mmwDemo_TransmitProcessedOutputTask` (see how type 601 does it in
   `mmwave_demo.c`).
2. Host: `DEFAULT_REGISTRY.register(your_id, your_parser)` — see the
   [Python API](python-api.md#custom-tlv-types).
