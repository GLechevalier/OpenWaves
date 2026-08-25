# Development handbooks

The condensed lab notebooks behind OpenWaves: what was built, in what
order, what broke, and how it got fixed. Read these to understand why the
firmware and the simulation look the way they do, or to retrace the steps
yourself.

- [Radar development handbook](development-handbook-radar.md) — from
  unboxing the IWRL6432BOOST to a full end-to-end chain in about five
  weeks: forking the TI demo into a custom firmware, rebuilding the DPC
  around Capon 3D heatmaps, streaming them over TLV, the ESP32 BLE
  bridge, the cloud classifier and the mobile app. Includes the
  beamforming trade study and the outcome vs the success criteria.
- [Electromagnetic simulation handbook](development-handbook-simulation.md)
  — building the openEMS simulation that generates training data without
  a bench: designing the 60 GHz patch antenna array and validating it
  against TI's measured patterns, replicating the hardware scene, the
  Gaussian-pulse transfer-function trick that turned 9-day FDTD runs
  into matrix multiplications, and the TX2 excitation bug hunt. Code in
  `hardware/electronics/electromagnetic_simulation/`.
