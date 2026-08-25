# IWRL6432 config reference

What every chirp/frame/DPC parameter does and the value the OpenWaves
firmware currently uses. Companion to [cli-commands.md](../cli-commands.md)
(the CLI syntax) and [mmwave-concepts.md](../mmwave-concepts.md) (the
theory). Values were derived with TI's sensing estimator.

## chirpComnCfg

| Parameter | Meaning | Ours |
|---|---|---|
| `DIG_OUT_SAMPLING_RATE` | ADC sample rate divider: rate = 100 MHz / N (valid N: 8..100, i.e. 12.5 MHz down to 1 MHz) | 8 (12.5 MHz) |
| `DIG_OUT_BITS_SEL` | Which 12/16 bits of the 16-bit DFE path go out (0 = 12 MSB after rounding, 5 = full 16 bit) | 0 |
| `DFE_FIR_SEL` | Final FIR: 0 = long filter, IF visible to 0.45 x fs; 1 = short filter, faster settling, 0.40 x fs | 0 |
| `NUM_ADC_SAMPLES` | ADC samples per chirp (powers of 2, up to 2048) | 256 |
| `MIMO_SEL` | TX MIMO pattern: 1 = TDM 2TX, 4 = BPM 2TX (0 = disabled, unsupported in OOB) | 4 (BPM) |
| `CHIRP_RAMP_END_TIME` | Ramp end time, common to all chirps (us) | 24.3 |
| `CHIRP_RX_HPF_SEL` | RX HPF corner: 0/1/2/3 = 175/350/700/1400 kHz | 3 (1400 kHz) |

## chirpTimingCfg

| Parameter | Meaning | Ours |
|---|---|---|
| `CHIRP_IDLE_TIME` | Idle time between chirps (us) | 28 |
| `CHIRP_ADC_START_TIME` | ADC start skip (samples, 0..63) | 37 |
| `CHIRP_TX_START_TIME` | TX start vs ramp knee (us) | 0 |
| `CHIRP_SLOPE` | FMCW slope (MHz/us, +-399 max) | 160 |
| `START_FREQ` | Chirp start frequency (GHz, 58..62.5 on ES1.0) | 58 |

With 160 MHz/us over 24.3 us the sweep covers ~58 to 61.9 GHz.

## channelCfg

| Parameter | Meaning | Ours |
|---|---|---|
| `RX_BITMASK` | RX antenna enable bitmask | 7 (all 3 RX) |
| `TX_BITMASK` | TX antenna enable bitmask | 3 (both TX) |
| `MISC_CTRL` | Unsupported in current SDK | 0 |

## frameCfg

| Parameter | Meaning | Ours |
|---|---|---|
| `NUM_CHIRPS_PER_BURST` | Chirps per burst (1..65535) | 64 |
| `NUM_CHIRPS_ACCUM` | Chirps accumulated in the DFE before output, free SNR without more DSP work (0..64) | 0 |
| `BURST_PERIOD` | Burst period (us) | 4000 |
| `NUM_BURSTS_PER_FRAME` | Bursts per frame (1..4096) | 1 |
| `FRAME_PERIOD` | Frame period (ms) | 100.0 |
| `NUM_FRAMES` | 0 = run forever | 0 |

## guiMonitor

One enable flag per TLV stream: point cloud, range profile
(major/minor/both), range-azimuth heatmap, stats, presence, raw ADC
samples, tracker, micro-Doppler, classifier, quick eval. OpenWaves runs
with everything off except `CAPONSPECTRUM3DHEATMAP_EN = 1`: the only
output is the Capon 3D heatmap.

## sigProcChainCfg

| Parameter | Meaning | Ours |
|---|---|---|
| `AZ_FFT_SIZE` / `EL_FFT_SIZE` | Azimuth / elevation FFT sizes (powers of 2) | 64 / 32 |
| `MOTDETMODE` | 1 = major motion only, 2 = minor, 3 = auto | 1 |
| `COHERENT_DOPP` | Doppler integration: 0 non-coherent, 1 coherent max, 2 mixed | 0 |
| minor-motion params | frames/chirps for minor motion, zero-velocity forcing, velocity threshold | 0 (unused) |

## caponBeamformingCfg

Azimuth angles sampled: 32 (of 32/64). Elevation angles sampled: 16 (of
16/32). Together with the range gating this defines the 10 x 32 x 16
heatmap the firmware streams (TLV 601).

## CFAR, FOV and misc processing

- **cfarCfg**: averaging mode 2, window 8, guard 4, noise divider shift 3,
  no cyclic mode, threshold 12.0 dB, peak grouping off, sidelobe threshold
  0.95, local max on Doppler only, interpolation on in both range and
  Doppler.
- **aoaFovCfg**: azimuth -80 to +80 deg, elevation -20 to +20 deg.
- **rangeSelCfg**: 0.1 to 10.0 m.
- **clutterRemoval**: off (we want the static wall reflections).
- **compRangeBiasAndRxChanPhase**: range bias 0.0, per-channel phase
  compensation alternating +1/-1 on the 6 virtual channels.
- **lowPowerCfg**: off.
- **compressionCfg**: enabled, ratio 0.5.

## antGeometryCfg

Virtual antenna grid positions (row, col) for the 6 channels:
(0,0), (1,1), (0,2), (0,1), (1,2), (0,3), with element spacing
2.418 mm (~ λ/2 at 60 GHz) in both X and Z.

## factoryCalibCfg

Save/restore factory calibration to QSPI flash. Save and restore are
mutually exclusive flags; calibration should be done at room temperature.
RX gain 40 dB (recommended range 30-40), TX backoff 0 dB, flash offset
0x1FF000 (last sector; must be above 0x100000 so it never overlaps the
app image, calibration data itself is 128 bytes).

## sensorStart

Frame trigger mode 0 (software immediate; the only mode the SDK currently
supports), loopback disabled, live monitors disabled, trigger timer 0.
