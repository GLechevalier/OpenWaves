# Troubleshooting

## Board not found (`PortNotFoundError`)

`openwaves ports` lists everything visible and marks what it recognized.

- **Windows**: Device Manager → Ports should show *XDS110 Class
  Application/User UART* and *XDS110 Class Auxiliary Data Port*. If not:
  different USB cable (data, not charge-only), different port, or install
  the XDS110 drivers (bundled with TI tools; usually Windows Update finds
  them).
- **Linux**: the ports are `/dev/ttyACM*` (VID:PID `0451:bef3`).
  Permission denied → `sudo usermod -aG dialout $USER` and re-login.
  If ModemManager grabs the port, add a udev rule or uninstall it.
- **Two boards**: `openwaves ports` shows both serial numbers;
  pick one with `find_radar_ports(serial_number="...")`.

## CLI does not answer (`CliTimeoutError`)

- SOP switches still in flash mode → set to **SOP_MODE2** (S1.1 ON,
  S1.2 OFF) and power-cycle ([table](flashing.md#the-sop-switches-the-one-manual-step)).
- The sensor is already streaming on that port (single-port firmware):
  binary data isn't a prompt. `openwaves reset` (warm reset) brings the
  CLI back.
- A previous run left the CLI at 1250000 baud while you opened at 115200
  → `openwaves reset`, or open at the high rate.

## `Error` answers to config lines (`CliCommandError`)

- `not recognized as a CLI command` → the command belongs to the *other*
  firmware (tracker commands need TI's MPD demo; see the
  [two-firmware note](cli-commands.md#two-firmwares-two-command-sets)).
  Type `help` in `openwaves term` to list what's actually flashed.
- Some commands only apply before `sensorStart` — send `sensorStop 0`
  first.

## No frames / `FrameSyncError`

- Config sent but `start()` not called (openwaves holds `sensorStart`
  back until you call it).
- Wrong stream: MPD firmware streams on the **data** port, the
  material-classification firmware on the **CLI** port. The facade
  auto-detects (`version` probe); force with `Radar(layout="single"|"dual")`.
- Baud mismatch on the data port: openwaves tries 1250000 then falls back
  to 921600 automatically. Some USB serial drivers reject the non-standard
  1250000 — change the cfg's `baudRate` line to `921600`.
- Garbage after a resync: one corrupted frame is reported in
  `frame.errors` and the parser rescans for the magic word; persistent
  garbage usually means baud mismatch.

## 1.25 Mbaud quirks

At `baudRate 1250000` the firmware's UART RX drops characters that arrive
back-to-back — every command (including `sensorWarmRst`) must be written
character-by-character with ~1 ms gaps. `RadarCli` does this automatically
above 1 Mbaud; keep it in mind if you talk to the port directly.

## Warm reset recovery

`sensorWarmRst 1` reboots the SoC: the CLI replies NUL bytes, the USB
ports drop and re-enumerate (possibly with new numbers). Use
`radar.warm_reset()` / `openwaves reset` — they close, wait, and re-detect.

## Flashing

See the [flashing guide](flashing.md#troubleshooting). Golden rule: MODE1
+ power-cycle to flash, MODE2 + power-cycle to run.

## Python environment

- `openwaves` needs Python ≥ 3.10; the demos' extras (torch, rerun-sdk,
  bleak) may lag the newest interpreter — 3.12 is the safe choice.
- `ImportError: bleak` → `pip install -e software/openwaves[ble]`.
- Rerun viewer doesn't open → `pip install -e software/openwaves[viz]`,
  and run scripts from their example directory (they use relative paths).

## Still stuck?

`openwaves -v <command>` prints debug logs (every CLI exchange, sync
scans, bootloader packets). Attach that output to a GitHub issue.
