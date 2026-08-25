# Physics

The theory behind the radar, bottom-up: what active RF devices are made
of, how a transceiver is architected, what happens when a wave hits a
wall, and how all of it maps to the parameters you set on the IWRL6432.

- [mmWave concepts](mmwave-concepts.md) — FMCW basics mapped to the
  `openwaves.config` parameters: range from bandwidth, velocity from
  chirps, angle from virtual antennas, CFAR, and why the OpenWaves
  firmware uses Capon beamforming. The practical entry point.
- [Wall radar theory](wall-radar-theory.md) — electromagnetic
  reflectometry: phase shift gives interface distances, reflected
  intensity gives the material, frequency sweeping enriches the
  signature, and why FMCW is the right technique for it.
- [Transceiver architecture](transceiver-architecture.md) — why receivers
  look the way they do: Friis formula (the LNA comes first), heterodyne
  downconversion, the image problem, the filtering trade-offs, PLLs.
- [Active devices](active-devices.md) — semiconductors from the PN
  junction up: N/P doping, FET vs BJT, and which material system (Si,
  GaAs, GaN, InP) fits which RF application.

Reading order for the curious: active devices → transceiver architecture
→ mmWave concepts → wall radar theory. Reading order for the impatient:
mmWave concepts, then back to the [guides](../README.md).
