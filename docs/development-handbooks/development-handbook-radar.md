# Phase 1 log

Concept validation on the IWRL6432BOOST: from unboxing to a full
end-to-end demo (radar → Capon 3D heatmap → BLE → phone → cloud
classifier) in about five weeks. This is the condensed lab notebook.

## Week 1: setup and first measurements

- Installed CCS 12+, STM32CubeIDE, mmWave SDK 4.13+, radar toolbox.
- Brought up the IWRL6432BOOST: USB power, UART at 115200, ran the
  out-of-box demo, verified motion detection and raw range-FFT data in
  TI's visualizer.
- Set up the STM32 Nucleo-F446RE as a companion dev board... and then
  realized we did not need the STM32 at all. The IWRL6432's Cortex-M4F
  runs everything standalone. Lesson kept for the record.
- Forked the OOB demo into a `material_analyzer` firmware: stripped
  multi-object tracking, configured for static short-range measurements
  (5-30 cm).

Key references collected: IWRL6432BOOST user guide (SWRU596), IWRL6432
datasheet, radar toolbox examples, TI's surface classification ML flow.

## Week 2: thickness algorithm and OLED

- Wall thickness estimation: more systematic trials needed, parked.
- Wired an SSD1306 OLED directly to the boosterpack I2C pins
  (3.3V/GND on J6, SCL/SDA on J7.9/J7.10), validated the driver on the
  STM32 first, then ported it to the IWRL6432.

## Weeks 3-4: a DPC that feeds a neural network

Goal: rebuild the data processing chain so the output is rich enough to
train on. Structure: ADC buffer → range FFT DPU → Capon beamforming
(3D power spectrum, no Doppler, which is fine, a post-Capon Doppler is
possible) → TLV output for recording.

Getting the 3D heatmap out over TLV meant touching:

- `mmwave_demo.h`: extend `DPC_ObjectDetection_ExecuteResult` and the
  MSS control block to carry the heatmap.
- `dpc.c`: allocate heatmap memory in `DPC_config`, assign results in
  `DPC_execute`.
- `mmwave_demo.c`: change what `mmwDemo_TransmitProcessedOutputTask`
  sends to the host.

Then the fun parts:

- Task priority conflicts, solved with semaphore ping-pong.
- Output packet too large, trimmed until the UART throughput was good.
  Possible future wins: run Capon on the HWA, use EDMA (could cut
  transfer time by ~10x).
- Recorder-side changes lived in the radar toolbox visualizer's
  `Applications_Visualizer/common`.

Trained a first two-class neural network on the recorded heatmaps:
works. Decided the production model would live in the cloud behind an
API rather than on-device (protects the model, keeps it updatable).
TI's TVM compilation flow exists but is Linux-only.

## Week 5: BLE bridge, cloud, app, validation

- **ESP32 bridge**: IWRL6432 UART (J8.5/J8.7, S1.4 ON) to ESP32
  GPIO16/17, then BLE to the iPhone. Packetized with a send queue, then
  replaced with a custom binary protocol decoded on the phone.
- **Cloud service**: API endpoint that takes the Capon 3D heatmap and
  returns the material class.
- **App**: React Native (Expo Go), receives BLE data from the ESP32 and
  forwards it to the classification API.
- Full-chain validation: it works.

## Beamforming algorithms, for the record

| Family | Complexity | Performance | Robustness |
|---|---|---|---|
| Conventional | Low | Medium | High |
| MVDR (Capon) | Medium | High | Medium |
| MUSIC | High | Very high | Low |
| ML-based | Very high | Adaptable | Very low |

Capon won: the best performance/robustness compromise the M4F can carry.

## Outcome vs criteria

Met: custom firmware with integrated algorithms, distance to +-2 cm over
5-25 cm, 3-material classification > 80%, OLED interface, BLE to mobile,
measurement database with export, real-time mobile interface, +-1 cm on
distance, 4+ materials > 85%. Not done: auto-calibration.
