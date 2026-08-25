# IWRL6432BOOST firmware

Firmware for the TI [IWRL6432BOOST](https://www.ti.com/tool/IWRL6432BOOST) mmWave devkit. [`material_classification/`](material_classification/) is a Code Composer Studio project based on the TI mmwave demo, modified to compute Capon 3D beamforming heatmaps on-chip (custom DPU in [`caponBeamforming2D_remake/`](material_classification/caponBeamforming2D_remake/)). `point_cloud/` is a placeholder.

## Flash the prebuilt image

No compilation and **no TI software** needed — the ready-to-flash Release
image ships inside the `openwaves` Python package
(`software/pyopenwaves/src/openwaves/firmware/mmwave_demo.Release.appimage`):

```
pip install -e software/pyopenwaves      # from the repo root, once
openwaves flash
```

The command walks you through the SOP switch flow (MODE1 to flash,
MODE2 to run) — full guide in [docs/flashing.md](../../../docs/flashing.md).
To flash your own build: `openwaves flash path\to\your.appimage`.

<details>
<summary>Fallback: TI's arprog flasher (needs MMWAVE-L-SDK at C:\ti\)</summary>

1. Power off the board and set the SOP switches to **SOP_MODE1** (device management mode): S1.2 OFF, S1.1 OFF. Power on.
2. Flash over UART (the **Application/User UART** COM port):

```
cd C:\ti\MMWAVE_L_SDK_05_05_03_00\tools\boot
python arprog_cmdline.py -p COM<N> -f <path-to-appimage> -s SFLASH -t META_IMAGE1
```

(on Linux the port is typically `/dev/ttyACM0`, and use `python3`)

3. When the progress bar completes, power off and switch to **SOP_MODE2** (functional mode): S1.2 OFF, S1.1 ON. Power on — the firmware now boots standalone.

</details>

SOP switch reference (S1.2, S1.1):

| Mode | Name | S1.2 | S1.1 |
|---|---|---|---|
| SOP_MODE1 | Device management (flashing) | OFF | OFF |
| SOP_MODE2 | Application / functional | OFF | ON |
| SOP_MODE3 | Test | ON | OFF |
| SOP_MODE4 | Debug | ON | ON |

## Rebuild from source

Prerequisites: **Code Composer Studio 12.7** and **MMWAVE-L-SDK 05.05.03.00**
installed at `C:\ti\`.

1. Copy [`material_classification/caponBeamforming2D_remake/`](material_classification/caponBeamforming2D_remake/) to `C:\ti\MMWAVE_L_SDK_05_05_03_00\source\alg\caponBeamforming2D_remake\` — the project references it there.
2. Import `material_classification/` into Code Composer Studio (Project → Import CCS Projects).
3. Build the **Release** configuration — it produces `Release/mmwave_demo.Release.appimage` (build output is gitignored).
4. Flash it: `openwaves flash material_classification\Release\mmwave_demo.Release.appimage`. If you want the new build to ship with the Python package, also copy it over `software/pyopenwaves/src/openwaves/firmware/mmwave_demo.Release.appimage`.

## Official docs

TI's full guide ships with the SDK: `C:\ti\MMWAVE_L_SDK_05_05_03_00\README_FIRST_xWRL6432.html` → *Getting Started → Flash a Hello World example* and *EVM Setup*.
