# IWRL6432 reference

Everything specific to the TI IWRL6432 chip and the IWRL6432BOOST board:
how to get firmware onto it, how to program it, how to configure it, and
what it sends back.

- [Flashing firmware](flashing.md) — one-command USB flashing with
  `openwaves flash`, SOP switch guide, no TI software needed.
- [IWRL6432 programming notes](iwrl6432-programming.md) — the SDK
  functions (logging, address translation, semaphores, SOC init), the
  memory map, the app control registers, and the bench gotchas (256 KB
  RAM, use the HWA for FFTs, I2C/UART concurrency).
- [IWRL6432 config reference](iwrl6432-config-reference.md) — every
  chirp/frame/DPC CLI parameter, what it does, and the values the
  OpenWaves firmware uses. Companion to the
  [CLI command reference](../cli-commands.md) and
  [mmWave concepts](../physics/mmwave-concepts.md).
- [TLV output format](tlv-format.md) — the UART frame format the radar
  streams, byte by byte, including the OpenWaves Capon 3D heatmap
  (TLV 601).
