# mmWave concepts, mapped to the config you'll write

A minimal tour of FMCW radar theory in terms of the actual
`openwaves.config` parameters. For depth, TI's "mmWave radar fundamentals"
materials are excellent; this page is the working summary.

## FMCW in one paragraph

The radar transmits *chirps* — tones sweeping linearly from
`chirp_rf_freq_start` (~60 GHz) upward at `chirp_rf_freq_slope` (MHz/µs)
for `chirp_ramp_end_time` (µs). Echoes mix with the outgoing chirp; a
target at range R produces a beat tone at frequency proportional to R.
An FFT over one chirp's `num_of_adc_samples` (the **range FFT**) turns
targets into peaks in range bins. Phase changes of those peaks across
chirps give velocity (**Doppler FFT**); phase differences across antennas
give angle.

## Range

- **Bandwidth** `B = slope × ramp_time` (e.g. 40 MHz/µs × 28 µs ≈ 1.1 GHz).
- **Range resolution** `ΔR = c / 2B` — ~13 cm at 1.1 GHz. More bandwidth,
  finer resolution (`ChirpTimingCfg.chirp_rf_freq_slope`,
  `ChirpComnCfg.chirp_ramp_end_time`).
- **Max range** is set by the ADC sample rate (100 MHz /
  `dig_output_samp_rate_decim`) and IF bandwidth; in practice gate it with
  `RangeSelCfg(min_meters, max_meters)`.

## Velocity (Doppler)

- Chirps repeat every `chirp_idle_time + ramp_time`; a frame carries
  `num_of_chirps_in_burst × num_of_bursts_in_frame` of them (`FrameCfg`).
- **Max unambiguous velocity** ∝ λ / (4 × chirp period); **velocity
  resolution** ∝ λ / (2 × frame's total chirping time). More chirps per
  frame → finer Doppler bins.
- Per-point radial velocity is the `doppler` column of `frame.points`
  (m/s, negative = approaching).

## Angle

- The IWRL6432 has 2 TX × 3 RX = **6 virtual antennas** (`ChannelCfg 7 3 0`,
  MIMO pattern in `ChirpComnCfg.chirp_tx_mimo_pat_sel`), arranged per
  `AntGeometryCfg` (element spacing ~λ/2 = 2.418 mm on this board).
- Azimuth/elevation FFT sizes come from `SigProcChainCfg`; the usable
  field of view is clipped by `AoaFovCfg`. Six elements → coarse (~20°)
  single-FFT resolution; that's why the OpenWaves firmware uses **Capon
  beamforming** instead for imaging (below).

## Detection: CFAR, clutter, major/minor motion

- **CFAR** (`CfarCfg`) declares a detection where a cell exceeds its
  neighbours' noise estimate by `threshold_scale` dB — the main
  sensitivity/false-alarm trade-off.
- **Clutter removal** (`ClutterRemoval`) subtracts the static (zero
  Doppler) component — keep it off to image walls and furniture.
- The xWRL6432 chain distinguishes **major motion** (walking) from
  **minor motion** (breathing-scale) — `SigProcChainCfg.mot_det_mode`
  selects major/minor/both; minor motion is what makes presence detection
  work on a "static" person.

## From detections to meaning

- **Point cloud** — CFAR detections with position, doppler, SNR
  (`frame.points`, streamed per `GuiMonitor`).
- **Tracking** (MPD firmware) — a group tracker clusters points into
  persistent targets (`trackingCfg`, `boundaryBox`, `gatingParam`, ...) →
  `frame.tracks`; per-point associations in `frame.track_indexes`.
- **µDoppler** — per-track velocity spectrum over time (`microDopplerCfg`)
  → gait/fall signatures; this feeds the fall-detection CNN.
- **Capon 3D heatmap** (OpenWaves firmware) — instead of point detections,
  an MVDR spatial power spectrum over a (10 × 32 × 16) grid
  (`frame.capon_heatmap`). Material layers change the reflected spectrum
  enough for a network to classify them — the material-classification demo.

## Rules of thumb when editing a `.cfg`

| Want | Touch |
|---|---|
| Finer range resolution | ↑ slope or ramp time (bandwidth) |
| See slower movements | ↑ chirps per frame, minor-motion mode |
| Higher frame rate | ↓ `frame_periodicity` (watch UART throughput — that's why configs end with `baudRate 1250000`) |
| Fewer false points | ↑ CFAR `threshold_scale`, tighten `aoaFovCfg` / `rangeSelCfg` |
| See static objects | `clutterRemoval 0` |
