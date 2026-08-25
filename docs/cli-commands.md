# Radar CLI command reference

The firmware exposes a line-based CLI on the Application/User UART
(115200 baud at boot). A `.cfg` file is just these commands in order;
`openwaves` sends them via `radar.configure(...)` /
`radar.send_command(...)`, or interactively with `openwaves term`.

Conventions: every command is answered with an echo, `Done` (or
`Error <code>`), and a fresh `mmwDemo:/>` prompt. Times are in
microseconds unless noted; the *typed model* column names the
`openwaves.config` dataclass that generates the line (— means the line is
kept as a `RawCommand`).

## Two firmwares, two command sets

- **material_classification** (in-repo, what `openwaves flash` installs):
  the commands below *without* the tracker section. Streams the capon 3D
  heatmap (TLV 601) on the CLI UART.
- **TI Motion and Presence Detection (MPD)** demo: adds the tracker /
  classifier commands and streams point clouds on the auxiliary data port.
  The `.cfg` files in `software/fall_detection_example/cfg/` target it.

Sending a tracker command to the material-classification firmware returns
`not recognized as a CLI command` — the package warns but still sends, so
either firmware can be driven. `openwaves.control` exposes both tables as
data (`MATERIAL_CLASSIFICATION_PROFILE`, `MPD_PROFILE`).

## Sensor control

| Command & arguments | Meaning | Typed model |
|---|---|---|
| `sensorStop <FrameStopMode>` | Stop framing. Mode 0 = stop at frame boundary. | `SensorStop` |
| `sensorStart <FrameTrigMode> <LoopBackEn> <FrameLivMonEn> <FrameTrigTimerVal>` | Start framing with the loaded config. Trigger 0 = software/free-running. | `SensorStart` |
| `sensorWarmRst <Reserved>` | Reboot the device (USB re-enumerates). Use `radar.warm_reset()` — at 1.25 Mbaud the characters must be paced. | via `warm_reset()` |
| `baudRate <baudRate>` | Re-init the CLI UART at a new rate (typ. `1250000` before `sensorStart` so the TLV stream fits). The host must reopen at the new rate — handled automatically. | `BaudRate` |
| `help` | List the commands this firmware actually supports. | — |

## RF front-end / chirp timing

These define the FMCW waveform — see [mmWave concepts](physics/mmwave-concepts.md)
for how they map to range/velocity resolution.

| Command & arguments | Meaning | Typed model |
|---|---|---|
| `channelCfg <RxChCtrlBitMask> <TxChCtrlBitMask> <MiscCtrl>` | Enable RX/TX antennas as bitmasks. `7 3 0` = 3 RX + 2 TX (all six virtual antennas). | `ChannelCfg` |
| `chirpComnCfg <DigOutputSampRate_Decim> <DigOutputBitsSel> <DfeFirSel> <NumOfAdcSamples> <ChirpTxMimoPatSel> <ChirpRampEndTime> <ChirpRxHpfSel>` | Common chirp settings: ADC decimation (sample rate = 100 MHz / decim), output bit format, digital front-end filter, samples per chirp, TX MIMO pattern (BPM/TDM), ramp duration (µs), RX high-pass corner. | `ChirpComnCfg` |
| `chirpTimingCfg <ChirpIdleTime> <ChirpAdcSkipSamples> <ChirpTxStartTime> <ChirpRfFreqSlope> <ChirpRfFreqStart>` | Idle time between chirps (µs), ADC samples skipped at ramp start, TX start time, slope (MHz/µs) and start frequency (GHz). Slope × ramp time = RF bandwidth = range resolution. | `ChirpTimingCfg` |
| `frameCfg <NumOfChirpsInBurst> <NumOfChirpsAccum> <BurstPeriodicity> <NumOfBurstsInFrame> <FramePeriodicity> <NumOfFrames>` | Frame structure: chirps per burst, accumulation, burst period (µs), bursts per frame, frame period (ms → frame rate), frame count (0 = infinite). | `FrameCfg` |
| `antGeometryCfg <row0> <col0> ... <row5> <col5> <antDistX (mm)> <antDistY (mm)>` | Virtual-antenna grid positions and element spacing — must match the physical antenna (defaults fit the OpenWaves board / EVM). | `AntGeometryCfg` |
| `factoryCalibCfg <save enable> <restore enable> <rxGain> <backoff0> <Flash offset>` | Save/restore factory calibration in serial flash at the given offset. | `FactoryCalibCfg` |
| `compRangeBiasAndRxChanPhase <rangeBias> <Re00> <Im00> ... <Re05> <Im05>` | Range bias + per-virtual-antenna phase compensation (from calibration). | — |
| `measureRangeBiasAndRxChanPhase <enabled> <targetDistance> <searchWin>` | Measure the values above with a corner reflector at a known distance. | — |
| `lowPowerCfg <LowPowerModeEnable>` | Enter low-power state between frames. | `LowPowerCfg` |

## Detection chain

| Command & arguments | Meaning | Typed model |
|---|---|---|
| `sigProcChainCfg <azimuthFftSize> <elevationFftSize> <motDetMode> <coherentDoppler> <numFrmPerMinorMotProc> <numMinorMotionChirpsPerFrame> <forceMinorMotionVelocityToZero> <minorMotionVelocityInclusionThr>` | Angle FFT sizes and the major/minor-motion processing mode (1 = major only, 2 = minor only, 3 = both). *Major* = moving targets, *minor* = sub-millimeter motion (breathing). | `SigProcChainCfg` |
| `cfarCfg <averageMode> <winLen> <guardLen> <noiseDiv> <cyclicMode> <thresholdScale> <peakGroupingEn> [...]` | CFAR detector: noise-averaging window/guard sizes and detection threshold (dB) — the main sensitivity knob. | `CfarCfg` |
| `cfarScndPassCfg <enabled> <averageMode> ...` | Optional second CFAR pass. | — |
| `aoaFovCfg <minAzimuthDeg> <maxAzimuthDeg> <minElevationDeg> <maxElevationDeg>` | Angular field of view — detections outside are dropped. | `AoaFovCfg` |
| `rangeSelCfg <minMeters> <maxMeters>` | Range gate. | `RangeSelCfg` |
| `clutterRemoval <0/1>` | Remove static clutter (zero-Doppler bin). Disable it to see walls/furniture. | `ClutterRemoval` |
| `sensorPosition <xOffset> <yOffset> <zOffset> <azimuthTilt> <elevationTilt>` | Sensor mounting pose (m, deg) used to put the point cloud in room coordinates. | `SensorPosition` |
| `guiMonitor <pointCloud> <rangeProfile> <noiseProfile> <rangeAzimuthHeatMap> <rangeDopplerHeatMap> <statsInfo> <presenceInfo> <adcSamples> <trackerInfo> <microDopplerInfo> <classifierInfo>` | Which TLVs to stream (0 = off; pointCloud 1 = uncompressed, 2 = compressed). The MPD demo takes an extra 12th flag. Maps to the [TLV types](iwrl6432-doc.md/tlv-format.md). | `GuiMonitor` |
| `adcDataSource <0-DFP, 1-File> <fileName>` | Live RF or replay from an ADC file (bench testing). | — |
| `adcLogging <0/1/2> ...` | Stream raw ADC out (DCA1000 or SPI). | — |
| `compressionCfg <enabled> <compressionRatio>` | Radar-cube compression (material_classification firmware). | — |

## Tracker / classifier (MPD firmware only)

| Command | Meaning |
|---|---|
| `trackingCfg <enable> <dimensionality> <maxNumPoints> <maxNumTracks> <maxRadialVelocity> <radialVelocityResolution> <deltaT>` | Group-tracker master switch and capacities. |
| `boundaryBox <xMin> <xMax> <yMin> <yMax> <zMin> <zMax>` | World-coordinate box; points outside are ignored by the tracker. |
| `staticBoundaryBox ...` | Where static (minor-motion) targets may be declared. |
| `presenceBoundaryBox ...` | Zone for the presence indication TLV. |
| `gatingParam <gain> <width> <depth> <height> <velocity>` | How far from a track new points may associate. |
| `stateParam <det2act> <det2free> <act2free> <stat2free> <exit2free> <sleep2free>` | Track state-machine frame counts. |
| `allocationParam <snr> <snrObscured> <velocity> <points> <maxDist> <maxVel>` | Thresholds to spawn a new track. |
| `maxAcceleration <x> <y> <z>` | Tracker motion-model limit (m/s²). |
| `microDopplerCfg <enabled> ...` | µDoppler spectrum extraction per track (TLV 310/311). |
| `classifierCfg <enabled> <minNumPntsPerTrack> <missTotFrmThre>` | On-chip human/non-human classifier (TLV 317). |

## RF monitors (production/diagnostics)

`enableRFmons`, `monPllCtrlVolt`, `monTxRxLbCfg`, `monTxnPowCfg`,
`monTxnBBPowCfg`, `monTxnDcSigCfg`, `monRxHpfDcSigCfg`, `monPmClkDcCfg` —
built-in RF self-monitors (TX power, loopback, PLL voltage, DC signal
paths). Not needed for normal operation; see TI's MMWAVE-L-SDK docs.

## Example, annotated

```
sensorStop 0                          % stop before reconfiguring
channelCfg 7 3 0                      % 3 RX + 2 TX
chirpComnCfg 16 0 0 128 4 28 3       % 128 samples, 28 µs ramp
chirpTimingCfg 6 32 0 40 60          % 40 MHz/µs from 60 GHz → ~1.1 GHz BW
frameCfg 2 0 200 64 100 0            % 64 bursts × 2 chirps, 10 FPS, forever
guiMonitor 2 0 0 0 0 0 0 0 1 1 0 0  % compressed points + tracker + µDoppler
trackingCfg 1 2 100 6 61.4 191.8 100 % MPD firmware: enable 3D tracker
baudRate 1250000                     % raise UART rate for the TLV stream
sensorStart 0 0 0 0                  % go
```
