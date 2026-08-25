# R&D notes

Summaries of the working documents behind the OpenWaves radar: course notes,
chip references, theory, and the development logs that led to the current
design. These are condensed from the original R&D docs, kept here so the
reasoning behind the hardware and firmware choices stays in the repo.

## Theory and courses

- [Active devices](active-devices.md) - semiconductors, N/P doping, the PN junction, FET vs BJT, and which material system (Si, GaAs, GaN, InP) fits which RF application.
- [Transceiver architecture](transceiver-architecture.md) - why receivers look the way they do: Friis formula, heterodyne downconversion, the image problem, PLLs.
- [Wall radar theory](wall-radar-theory.md) - the physics of measuring wall thickness and material type with electromagnetic reflectometry.

## IWRL6432 references

- [IWRL6432 programming notes](iwrl6432-programming.md) - the SDK functions, semaphores, memory map and registers you touch when writing firmware.
- [IWRL6432 config reference](iwrl6432-config-reference.md) - every chirp/frame/DPC CLI parameter, what it does, and the values the OpenWaves firmware uses.

## Development history

- [Roadmap and architecture study](development-roadmap.md) - the original plan, the component/architecture trade study, and why a 60 GHz monostatic FMCW radar-on-chip won.
- [Phase 1 log](phase1-log.md) - from unboxing the IWRL6432BOOST to a working end-to-end demo: custom firmware, Capon heatmaps over TLV, ESP32 BLE bridge, cloud classifier, mobile app.
- [Phase 1.5 log](phase1_5-simulation.md) - building the openEMS electromagnetic simulation to generate training data without a bench.
