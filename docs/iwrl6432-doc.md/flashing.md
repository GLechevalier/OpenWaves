# Flashing firmware

`openwaves flash` writes an `.appimage` to the board's serial flash over
USB, using a built-in implementation of the xWRL6432 ROM UART bootloader.
**No TI software is required** — not the SDK, not UniFlash, not CCS.

```bash
openwaves flash                          # bundled material-classification firmware
openwaves flash path/to/your.appimage    # any image (e.g. your own CCS build)
openwaves flash --port COM11             # skip port autodetection
openwaves flash --erase                  # erase serial flash first
```

In VSCode: **Terminal → Run Task → "Radar: Flash prebuilt firmware"**.

## The SOP switches (the one manual step)

The radar chip samples its SOP (Sense-On-Power) pins at boot to decide
between running the application and entering the flash-mode bootloader.
They are physical DIP switches on the IWRL6432BOOST (S1), so flashing
involves flipping them — no way around it, the flasher walks you through it:

| Mode | Purpose | S1.2 | S1.1 |
|---|---|---|---|
| **SOP_MODE1** | Device management — **flashing** | OFF | OFF |
| **SOP_MODE2** | Application / functional — **normal use** | OFF | ON |
| SOP_MODE3 | Test | ON | OFF |
| SOP_MODE4 | Debug (JTAG) | ON | ON |

Full flow:

1. Unplug USB. Set the switches to **SOP_MODE1** (both OFF). Plug back in.
2. Run `openwaves flash`. When it says *"Waiting for the bootloader"*,
   press the board's **RESET** button (or re-plug USB) — the ROM detects
   the flasher during boot and the progress bar runs.
3. Unplug USB. Set the switches back to **SOP_MODE2**. Plug back in.
   The new firmware boots; `openwaves ports` finds the CLI again.

## What is an `.appimage`?

The flashable container produced by a TI MMWAVE-L-SDK build: the
application binary (RPRC), the RF-firmware patch, and CRCs, packed as
`META_IMAGE1` for the bootloader. The package bundles the Release build of
the in-repo firmware (`openwaves.firmware.get_bundled_appimage()` gives its
path). To build your own, see the
[firmware README](../../hardware/firmware/IWRL6432BOOST_firmware/README.md).

## Flashing from Python

```python
from openwaves import flash_firmware

flash_firmware()                       # bundled image, autodetected port
flash_firmware("my.appimage", port="COM11",
               progress=lambda sent, total: print(sent, "/", total))
```

`openwaves.flash.BootloaderClient` exposes the lower-level protocol
(ping, version, erase, per-slot downloads) if you need it.

## Troubleshooting

| Symptom | Fix |
|---|---|
| *"No answer from the bootloader"* | SOP switches not in MODE1, or the board wasn't reset while the flasher waited. Check the switch table above and re-plug USB during the wait. |
| *"Bootloader refused ... (status 0x...)"* | The device NACKed. Try `--erase`, check the image is a valid `.appimage`, power-cycle and retry. |
| Wrong port | The bootloader talks on the **Application/User UART** (the CLI port, lower COM number). `openwaves ports` labels it. |
| Flash works but no CLI afterwards | Switches still in MODE1 — set back to MODE2 and power-cycle. |

## Fallback: TI's own flasher

The classic path still works if you have the MMWAVE-L-SDK installed and
want a second opinion:

```
cd C:\ti\MMWAVE_L_SDK_05_05_03_00\tools\boot
python arprog_cmdline.py -p COM<N> -f <image>.appimage -s SFLASH -t META_IMAGE1
```

## License note

The `.appimage` images embed TI MMWAVE-L-SDK components (RF firmware patch,
SDK libraries) which remain under TI's software license; the OpenWaves
sources are GPL-3.0.
