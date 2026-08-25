################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Add inputs and outputs from these tool invocations to the build variables 
CMD_SRCS += \
../linker.cmd 

SYSCFG_SRCS += \
../example.syscfg 

LIB_SRCS += \
C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D/lib/alg_caponBeamforming2D.xwrL64xx.m4f.ti-arm-clang.debug.lib 

C_SRCS += \
../ADC_testbuf.c \
C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D_remake/caponBeamforming2D.c \
../dpc.c \
./syscfg/ti_dpl_config.c \
./syscfg/ti_drivers_config.c \
./syscfg/ti_drivers_open_close.c \
./syscfg/ti_pinmux_config.c \
./syscfg/ti_power_clock_config.c \
./syscfg/ti_board_config.c \
./syscfg/ti_board_open_close.c \
../factory_cal.c \
../interrupts.c \
../main.c \
../mmw_cli.c \
../mmw_demo_utils.c \
../mmw_flash_cal.c \
../mmwave_control_config.c \
../mmwave_demo.c \
../monitors.c \
../power_management.c \
../range_phase_bias_measurement.c 

GEN_FILES += \
./syscfg/ti_dpl_config.c \
./syscfg/ti_drivers_config.c \
./syscfg/ti_drivers_open_close.c \
./syscfg/ti_pinmux_config.c \
./syscfg/ti_power_clock_config.c \
./syscfg/ti_board_config.c \
./syscfg/ti_board_open_close.c 

GEN_MISC_DIRS += \
./syscfg 

C_DEPS += \
./ADC_testbuf.d \
./caponBeamforming2D.d \
./caponBeamforming2D_precise.d \
./dpc.d \
./syscfg/ti_dpl_config.d \
./syscfg/ti_drivers_config.d \
./syscfg/ti_drivers_open_close.d \
./syscfg/ti_pinmux_config.d \
./syscfg/ti_power_clock_config.d \
./syscfg/ti_board_config.d \
./syscfg/ti_board_open_close.d \
./factory_cal.d \
./interrupts.d \
./main.d \
./mmw_cli.d \
./mmw_demo_utils.d \
./mmw_flash_cal.d \
./mmwave_control_config.d \
./mmwave_demo.d \
./monitors.d \
./power_management.d \
./range_phase_bias_measurement.d 

OBJS += \
./ADC_testbuf.o \
./caponBeamforming2D.o \
./dpc.o \
./syscfg/ti_dpl_config.o \
./syscfg/ti_drivers_config.o \
./syscfg/ti_drivers_open_close.o \
./syscfg/ti_pinmux_config.o \
./syscfg/ti_power_clock_config.o \
./syscfg/ti_board_config.o \
./syscfg/ti_board_open_close.o \
./factory_cal.o \
./interrupts.o \
./main.o \
./mmw_cli.o \
./mmw_demo_utils.o \
./mmw_flash_cal.o \
./mmwave_control_config.o \
./mmwave_demo.o \
./monitors.o \
./power_management.o \
./range_phase_bias_measurement.o 

GEN_MISC_FILES += \
./syscfg/ti_dpl_config.h \
./syscfg/ti_drivers_config.h \
./syscfg/ti_drivers_open_close.h \
./syscfg/ti_board_config.h \
./syscfg/ti_board_open_close.h \
./syscfg/ti_cli_mmwave_demo_config.h 

GEN_MISC_DIRS__QUOTED += \
"syscfg" 

OBJS__QUOTED += \
"ADC_testbuf.o" \
"caponBeamforming2D.o" \
"dpc.o" \
"syscfg\ti_dpl_config.o" \
"syscfg\ti_drivers_config.o" \
"syscfg\ti_drivers_open_close.o" \
"syscfg\ti_pinmux_config.o" \
"syscfg\ti_power_clock_config.o" \
"syscfg\ti_board_config.o" \
"syscfg\ti_board_open_close.o" \
"factory_cal.o" \
"interrupts.o" \
"main.o" \
"mmw_cli.o" \
"mmw_demo_utils.o" \
"mmw_flash_cal.o" \
"mmwave_control_config.o" \
"mmwave_demo.o" \
"monitors.o" \
"power_management.o" \
"range_phase_bias_measurement.o" 

GEN_MISC_FILES__QUOTED += \
"syscfg\ti_dpl_config.h" \
"syscfg\ti_drivers_config.h" \
"syscfg\ti_drivers_open_close.h" \
"syscfg\ti_board_config.h" \
"syscfg\ti_board_open_close.h" \
"syscfg\ti_cli_mmwave_demo_config.h" 

C_DEPS__QUOTED += \
"ADC_testbuf.d" \
"caponBeamforming2D.d" \
"caponBeamforming2D_precise.d" \
"dpc.d" \
"syscfg\ti_dpl_config.d" \
"syscfg\ti_drivers_config.d" \
"syscfg\ti_drivers_open_close.d" \
"syscfg\ti_pinmux_config.d" \
"syscfg\ti_power_clock_config.d" \
"syscfg\ti_board_config.d" \
"syscfg\ti_board_open_close.d" \
"factory_cal.d" \
"interrupts.d" \
"main.d" \
"mmw_cli.d" \
"mmw_demo_utils.d" \
"mmw_flash_cal.d" \
"mmwave_control_config.d" \
"mmwave_demo.d" \
"monitors.d" \
"power_management.d" \
"range_phase_bias_measurement.d" 

GEN_FILES__QUOTED += \
"syscfg\ti_dpl_config.c" \
"syscfg\ti_drivers_config.c" \
"syscfg\ti_drivers_open_close.c" \
"syscfg\ti_pinmux_config.c" \
"syscfg\ti_power_clock_config.c" \
"syscfg\ti_board_config.c" \
"syscfg\ti_board_open_close.c" 

C_SRCS__QUOTED += \
"../ADC_testbuf.c" \
"C:/ti/MMWAVE_L_SDK_05_05_03_00/source/alg/caponBeamforming2D_remake/caponBeamforming2D.c" \
"../dpc.c" \
"./syscfg/ti_dpl_config.c" \
"./syscfg/ti_drivers_config.c" \
"./syscfg/ti_drivers_open_close.c" \
"./syscfg/ti_pinmux_config.c" \
"./syscfg/ti_power_clock_config.c" \
"./syscfg/ti_board_config.c" \
"./syscfg/ti_board_open_close.c" \
"../factory_cal.c" \
"../interrupts.c" \
"../main.c" \
"../mmw_cli.c" \
"../mmw_demo_utils.c" \
"../mmw_flash_cal.c" \
"../mmwave_control_config.c" \
"../mmwave_demo.c" \
"../monitors.c" \
"../power_management.c" \
"../range_phase_bias_measurement.c" 

SYSCFG_SRCS__QUOTED += \
"../example.syscfg" 


