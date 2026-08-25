################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Each subdirectory must supply rules for building sources it contributes
%.o: ../%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: Arm Compiler'
	"C:/ti/ccs1271/ccs/tools/compiler/ti-cgt-armllvm_3.2.2.LTS/bin/tiarmclang.exe" -c -mcpu=cortex-m4 -mfloat-abi=hard -mlittle-endian -mthumb -I"C:/ti/ccs1271/ccs/tools/compiler/ti-cgt-armllvm_3.2.2.LTS/include/c" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/dpc" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/test" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/mmwave_control" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/power_management" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/calibrations" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/utils" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/kernel/freertos/FreeRTOS-Kernel/include" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/kernel/freertos/portable/TI_ARM_CLANG/ARM_CM4F" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/kernel/freertos/config/xwrL64xx/m4f" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/firmware/mmwave_dfp" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D_remake" -DSOC_XWRL64XX -DGTRACK_3D=1 -DTRACKER_MAX_NUM_TR=10 -D_DEBUG_=1 -g -Wall -Wno-gnu-variable-sized-type-not-at-end -Wno-unused-function -mno-unaligned-access -MMD -MP -MF"$(basename $(<F)).d_raw" -MT"$(@)" -I"C:/Users/gauth/workspace_v12/dpc_chain_test/mmwave_demo_xwrL64xx-evm_m4fss0-0_freertos_ti-arm-clang/Debug/syscfg"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

caponBeamforming2D.o: C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D_remake/caponBeamforming2D.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: Arm Compiler'
	"C:/ti/ccs1271/ccs/tools/compiler/ti-cgt-armllvm_3.2.2.LTS/bin/tiarmclang.exe" -c -mcpu=cortex-m4 -mfloat-abi=hard -mlittle-endian -mthumb -I"C:/ti/ccs1271/ccs/tools/compiler/ti-cgt-armllvm_3.2.2.LTS/include/c" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/dpc" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/test" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/mmwave_control" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/power_management" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/calibrations" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/utils" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/kernel/freertos/FreeRTOS-Kernel/include" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/kernel/freertos/portable/TI_ARM_CLANG/ARM_CM4F" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/kernel/freertos/config/xwrL64xx/m4f" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/firmware/mmwave_dfp" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D_remake" -DSOC_XWRL64XX -DGTRACK_3D=1 -DTRACKER_MAX_NUM_TR=10 -D_DEBUG_=1 -g -Wall -Wno-gnu-variable-sized-type-not-at-end -Wno-unused-function -mno-unaligned-access -MMD -MP -MF"$(basename $(<F)).d_raw" -MT"$(@)" -I"C:/Users/gauth/workspace_v12/dpc_chain_test/mmwave_demo_xwrL64xx-evm_m4fss0-0_freertos_ti-arm-clang/Debug/syscfg"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

build-79440977: ../example.syscfg
	@echo 'Building file: "$<"'
	@echo 'Invoking: SysConfig'
	"C:/ti/ccs1271/ccs/utils/sysconfig_1.20.0/sysconfig_cli.bat" --script "C:/Users/gauth/workspace_v12/dpc_chain_test/mmwave_demo_xwrL64xx-evm_m4fss0-0_freertos_ti-arm-clang/example.syscfg" -o "syscfg" -s "C:/ti/MMWAVE_L_SDK_05_05_03_00/.metadata/product.json" --context "m4fss0-0" --part Default --package FCCSP --compiler ticlang
	@echo 'Finished building: "$<"'
	@echo ' '

syscfg/ti_dpl_config.c: build-79440977 ../example.syscfg
syscfg/ti_dpl_config.h: build-79440977
syscfg/ti_drivers_config.c: build-79440977
syscfg/ti_drivers_config.h: build-79440977
syscfg/ti_drivers_open_close.c: build-79440977
syscfg/ti_drivers_open_close.h: build-79440977
syscfg/ti_pinmux_config.c: build-79440977
syscfg/ti_power_clock_config.c: build-79440977
syscfg/ti_board_config.c: build-79440977
syscfg/ti_board_config.h: build-79440977
syscfg/ti_board_open_close.c: build-79440977
syscfg/ti_board_open_close.h: build-79440977
syscfg/ti_cli_mmwave_demo_config.h: build-79440977
syscfg: build-79440977

syscfg/%.o: ./syscfg/%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: Arm Compiler'
	"C:/ti/ccs1271/ccs/tools/compiler/ti-cgt-armllvm_3.2.2.LTS/bin/tiarmclang.exe" -c -mcpu=cortex-m4 -mfloat-abi=hard -mlittle-endian -mthumb -I"C:/ti/ccs1271/ccs/tools/compiler/ti-cgt-armllvm_3.2.2.LTS/include/c" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/dpc" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/test" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/mmwave_control" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/power_management" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/calibrations" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/examples/mmw_demo/mmwave_demo/source/utils" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/kernel/freertos/FreeRTOS-Kernel/include" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/kernel/freertos/portable/TI_ARM_CLANG/ARM_CM4F" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/kernel/freertos/config/xwrL64xx/m4f" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/firmware/mmwave_dfp" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D" -I"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D_remake" -DSOC_XWRL64XX -DGTRACK_3D=1 -DTRACKER_MAX_NUM_TR=10 -D_DEBUG_=1 -g -Wall -Wno-gnu-variable-sized-type-not-at-end -Wno-unused-function -mno-unaligned-access -MMD -MP -MF"syscfg/$(basename $(<F)).d_raw" -MT"$(@)" -I"C:/Users/gauth/workspace_v12/dpc_chain_test/mmwave_demo_xwrL64xx-evm_m4fss0-0_freertos_ti-arm-clang/Debug/syscfg"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '


