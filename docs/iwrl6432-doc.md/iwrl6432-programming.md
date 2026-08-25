# IWRL6432 programming notes

The SDK functions, patterns and addresses you actually touch when writing
firmware for the IWRL6432. Condensed from the working notes; the full
register list lives in the SDK headers (`cslr_soc_baseaddress.h`,
`cslr_app_ctrl.h`).

## Everyday functions

- **Print from the board**: `DebugP_log()` behaves like `printf` but runs
  on the target.
- **Address translation**: `AddrTranslateP_getLocalAddr(systemAddr)`
  converts a system address into the CPU-local view. Typical use:

  ```c
  gpioBaseAddr = (uint32_t) AddrTranslateP_getLocalAddr(CSL_APP_GIO_U_BASE);
  GPIO_pinWriteHigh(gpioBaseAddr, 5);
  ```

- **Sleep**: `ClockP_sleep(delaySec)` sleeps for whole seconds.
- **Counting semaphore**:
  `SemaphoreP_constructCounting(&obj, initValue, maxValue)` returns
  `SystemP_SUCCESS` or `SystemP_FAILURE`. Semaphore functions take a
  `SemaphoreP_Object`.
- **SOC init**: `SOC_memoryInit(flag)` initializes the APPSS shared RAM0/1
  and the HWASS shared RAM, the memories shared between the CPU and the
  hardware accelerator.

Return convention everywhere: `int32_t`, `SystemP_SUCCESS` /
`SystemP_FAILURE`.

## Memory map highlights

The bases you use most (all from `cslr_soc_baseaddress.h`):

| Block | Symbol | Address |
|---|---|---|
| CPU RAM (512 KB) | `CSL_APP_CPU_RAM_U_BASE` | 0x00400000 |
| CPU shared RAM (256 KB) | `CSL_APP_CPU_SHARED_RAM_U_BASE` | 0x00480000 |
| FEC RAM / shared RAM | `CSL_FEC_RAM_U_BASE` | 0x21200000 / 0x21208000 |
| FEC control | `CSL_FEC_CTRL_U_BASE` | 0x52000000 |
| HWA RAM | `CSL_APP_HWA_RAM_U_BASE` | 0x60000000 |
| HWA ADC buffer read / write | `CSL_APP_HWA_ADCBUF_RD/WR_U_BASE` | 0x55060000 / 0x55070000 |
| HWA config, param, window RAM | `CSL_APP_HWA_*` | 0x55010000 region |
| EDMA (TPCC A / B) | `CSL_APP_TPCC_A/B_U_BASE` | 0x56000000 / 0x55080000 |
| App control | `CSL_APP_CTRL_U_BASE` | 0x56060000 |
| UART0 / UART1 | `CSL_APP_UART0/1_U_BASE` | 0x53F7F000 / 0x57F7F000 |
| I2C | `CSL_APP_I2C_U_BASE` | 0x57F7F800 |
| GPIO | `CSL_APP_GIO_U_BASE` | 0x5AF7FC00 |
| SPI0 / SPI1 | `CSL_MCU_MCSPI0/1_CFG_BASE` | 0x53F7F400 / 0x57F7F400 |
| QSPI config / external flash | `CSL_APP_CFG_QSPI_U_BASE` / `CSL_APP_QSPI_EXT_FLASH_U_BASE` | 0x78000000 / 0x70000000 |
| Frame counter | `CSL_FRAME_COUNTER_U_BASE` | 0x5B000000 |

## App control registers (`cslr_app_ctrl.h`)

Offsets relative to `CSL_APP_CTRL_U_BASE` (0x56060000). The interesting
groups:

- **IDs and scratch**: `PID` (0x00, resets to 0x61800214), `HW_REG0-7`,
  spare RW/RO registers.
- **Memory init**: `APPSS_RAM1A/2A/3A_MEM_INIT[_DONE/_STATUS]`,
  `HWASS_SHRD_RAM0/1_MEM_INIT[...]`, `APPSS_TPCC_MEMINIT_*`. Kick the init,
  poll DONE.
- **Peripheral config**: `APPSS_SPIA/SPIB_CFG`, `APPSS_EPWM_CFG`,
  `APPSS_QSPI_CONFIG`, SPI IO config, MCAN interrupt clear/mask/status.
- **Interrupts and DMA routing**: `APPSS_SW_INT`, `APPSS_IRQ_REQ_SEL`,
  `APPSS_DMA_REQ_SEL`, `APPSS_DMA1_REQ_SEL`, TPCC A/B error and interrupt
  aggregators (mask/status/raw).
- **Error handling**: ESM gating registers, error aggregators
  (`APPSS_ERRAGG_MASK0/1`, `APPSS_MPU_ERRAGG_*`), RAM overwrite error
  address capture, fault address/type/attribute/clear block at 0x1024+.
- **Clocks and power**: `FECSS_CLK_GATE`, `HWASS_CLK_GATE`,
  `APPSS_SHARED_MEM_CLK_GATE`, WIC control/status, force FCLK/HCLK active.
- **Boot info**: `APPSS_BOOT_INFO_REG0-7`.

## Gotchas from the bench

- CPU is a Cortex-M4F at 160 MHz with 256 KB app RAM: keep radar buffers
  small, stream over UART instead of storing, use flash for logs.
- Use the HWA for FFTs, not the CPU; prefer fixed-point and the CMSIS-DSP
  library; watch interrupt priorities.
- Running I2C (OLED) and UART (BLE, debug) together needs a task scheduler,
  circular buffers, explicit priorities (display > Bluetooth > debug) and
  timeouts on every transaction.
