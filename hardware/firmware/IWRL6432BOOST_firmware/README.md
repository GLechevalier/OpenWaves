# IWRL6432BOOST firmware

Firmware for the TI [IWRL6432BOOST](https://www.ti.com/tool/IWRL6432BOOST) mmWave devkit. [`material_classification/`](material_classification/) is a Code Composer Studio project based on the TI mmwave demo, modified to compute Capon 3D beamforming heatmaps on-chip (custom DPU in [`caponBeamforming2D_remake/`](material_classification/caponBeamforming2D_remake/)). `point_cloud/` is a placeholder.

## Prerequisites

- **MMWAVE-L-SDK 05.05.03.00** installed at `C:\ti\` — [download from TI](https://www.ti.com/tool/MMWAVE-L-SDK)
- **Python 3** — used by TI's flashing script
- **Micro-USB** on the board's XDS110 port — it enumerates two COM ports; flashing uses the **Application/User UART** one (check Device Manager)
- **Code Composer Studio** — only if you rebuild from source

## Flash the prebuilt image

No compilation needed — the ready-to-flash image is committed at [`material_classification/Release/mmwave_demo.Release.appimage`](material_classification/Release/mmwave_demo.Release.appimage).

1. Power off the board and set the SOP switches to **SOP_MODE1** (device management mode): S1.2 OFF, S1.1 OFF. Power on.
2. Flash over UART:

```
cd C:\ti\MMWAVE_L_SDK_05_05_03_00\tools\boot
python arprog_cmdline.py -p COM<N> -f <path-to-repo>\hardware\firmware\IWRL6432BOOST_firmware\material_classification\Release\mmwave_demo.Release.appimage -s SFLASH -t META_IMAGE1
```

(on Linux the port is typically `/dev/ttyUSB0`, and use `python3`)

3. When the progress bar completes, power off and switch to **SOP_MODE2** (functional mode): S1.2 OFF, S1.1 ON. Power on — the firmware now boots standalone.

SOP switch reference (S1.2, S1.1):

| Mode | Name | S1.2 | S1.1 |
|---|---|---|---|
| SOP_MODE1 | Device management (flashing) | OFF | OFF |
| SOP_MODE2 | Application / functional | OFF | ON |
| SOP_MODE3 | Test | ON | OFF |
| SOP_MODE4 | Debug | ON | ON |

## Rebuild from source

1. Copy [`material_classification/caponBeamforming2D_remake/`](material_classification/caponBeamforming2D_remake/) to `C:\ti\MMWAVE_L_SDK_05_05_03_00\source\alg\caponBeamforming2D_remake\` — the project references it there.
2. Import `material_classification/` into Code Composer Studio (Project → Import CCS Projects).
3. Build the **Release** configuration — it produces `Release/mmwave_demo.Release.appimage`.
4. Flash as above.

## Official docs

TI's full guide ships with the SDK: `C:\ti\MMWAVE_L_SDK_05_05_03_00\README_FIRST_xWRL6432.html` → *Getting Started → Flash a Hello World example* and *EVM Setup*.
