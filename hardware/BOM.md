# Bill of Materials

Everything needed to build one OpenWaves radar unit. Prefer not to source and solder it all yourself? Grab a pre-assembled devkit — see the [README](../README.md#get-the-hardware).

## Radar unit

| # | Part | Qty | Reference | Notes |
|---|------|-----|-----------|-------|
| 1 | ESP32 dev board | 1 | `TBD — exact module/devboard part number` | Runs the firmware, streams heatmaps over BLE |
| 2 | mmWave radar front-end | 1 | `TBD — transceiver part number` | Paired with the custom antenna below |
| 3 | Antenna PCB | 1 | [`electronics/antenna_design/`](electronics/antenna_design/) | Custom design, simulated in [`electronics/electromagnetic_simulation/`](electronics/electromagnetic_simulation/) |
| 4 | LiPo battery | 1 | `TBD — capacity / part number` | Fits the battery casing variant |
| 5 | Push button | 1 | `TBD` | Mounts in the casing button assembly |
| 6 | 3D-printed casing | 1 set | [`mechanical_casing/v1/`](mechanical_casing/v1/) | PETG recommended for the body, PLA fine for the frame; print profiles (`.bgcode`) included for a Prusa MK4S |
| 7 | Fasteners | `TBD` | `TBD` | Screws for casing assembly |

## Fall detection demo (off the shelf)

| Part | Qty | Notes |
|------|-----|-------|
| TI IWRL6432BOOST evaluation board | 1 (2 for dual-radar room visualization) | CE-marked; available from [TI](https://www.ti.com) and usual distributors |

> `TBD` entries need exact part numbers filled in.
