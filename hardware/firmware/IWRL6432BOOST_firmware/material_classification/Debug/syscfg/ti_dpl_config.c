/*
 *  Copyright (C) 2021 Texas Instruments Incorporated
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions
 *  are met:
 *
 *    Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 *    Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the
 *    distribution.
 *
 *    Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 *  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 *  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 *  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 *  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 *  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 *  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 *  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 *  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
/*
 * Auto generated file 
 */
#include <stdio.h>
#include <drivers/soc.h>
#include <kernel/dpl/AddrTranslateP.h>
#include "ti_dpl_config.h"
#include "ti_drivers_config.h"


/* ----------- ClockP ----------- */
#define M4_SYSTICK_BASE_ADDR     (0xE000E010u)

ClockP_Config gClockConfig = {
    .timerBaseAddr = M4_SYSTICK_BASE_ADDR, 
    .timerHwiIntNum = 15,
    .timerInputClkHz = 160000000,
    .timerInputPreScaler = 1,
    .usecPerTick = 1000,
};

/* ----------- DebugP ----------- */

void putchar_(char character)
{
    /* Output to CCS console */
    putchar(character);
}



/* ----------- MpuP_armv7 ----------- */
#define CONFIG_MPU_NUM_REGIONS  (4u)

MpuP_Config gMpuConfig = {
    .numRegions = CONFIG_MPU_NUM_REGIONS,
    .enableBackgroundRegion = 0,
    .enableMpu = 1,
};

MpuP_RegionConfig gMpuRegionConfig[CONFIG_MPU_NUM_REGIONS] =
{
    {
        .baseAddr = 0x0u,
        .size = MpuP_RegionSize_4G,
        .attrs = {
            .isEnable = 1,
            .isCacheable = 0,
            .isBufferable = 0,
            .isSharable = 1,
            .isExecuteNever = 1,
            .tex = 0,
            .accessPerm = MpuP_AP_ALL_RW,
            .subregionDisableMask = 0x0u
        },
    },
    {
        .baseAddr = 0x400000u,
        .size = MpuP_RegionSize_512K,
        .attrs = {
            .isEnable = 1,
            .isCacheable = 1,
            .isBufferable = 1,
            .isSharable = 0,
            .isExecuteNever = 0,
            .tex = 1,
            .accessPerm = MpuP_AP_ALL_RW,
            .subregionDisableMask = 0x0u
        },
    },
    {
        .baseAddr = 0x22400000u,
        .size = MpuP_RegionSize_512K,
        .attrs = {
            .isEnable = 1,
            .isCacheable = 1,
            .isBufferable = 1,
            .isSharable = 0,
            .isExecuteNever = 0,
            .tex = 1,
            .accessPerm = MpuP_AP_ALL_RW,
            .subregionDisableMask = 0x0u
        },
    },
    {
        .baseAddr = 0x0u,
        .size = MpuP_RegionSize_256K,
        .attrs = {
            .isEnable = 1,
            .isCacheable = 1,
            .isBufferable = 1,
            .isSharable = 0,
            .isExecuteNever = 0,
            .tex = 1,
            .accessPerm = MpuP_AP_ALL_R,
            .subregionDisableMask = 0x0u
        },
    },
};

/* ----------- TimerP ----------- */
#define CONFIG_TIMER0_CLOCK_SRC_MUX_ADDR (0x56040034u)
#define CONFIG_TIMER0_CLOCK_SRC_OSC_CLK (0x0u)


HwiP_Object gTimerHwiObj[TIMER_NUM_INSTANCES];
uint32_t gTimerBaseAddr[TIMER_NUM_INSTANCES];

void TimerP_isr0(void *args)
{
    TimerP_clearOverflowInt(gTimerBaseAddr[CONFIG_TIMER0]);
    HwiP_clearInt(CONFIG_TIMER0_INT_NUM);
}

void TimerP_init()
{
    TimerP_Params timerParams;
    HwiP_Params timerHwiParams;
    int32_t status;

    /* set timer clock source */
    SOC_controlModuleUnlockMMR(SOC_DOMAIN_ID_APP_RCM, 0);
    *(volatile uint32_t*)AddrTranslateP_getLocalAddr(CONFIG_TIMER0_CLOCK_SRC_MUX_ADDR) = CONFIG_TIMER0_CLOCK_SRC_OSC_CLK;
    SOC_controlModuleLockMMR(SOC_DOMAIN_ID_APP_RCM, 0);

    gTimerBaseAddr[CONFIG_TIMER0] = (uint32_t)AddrTranslateP_getLocalAddr(CONFIG_TIMER0_BASE_ADDR);
    CSL_REG32_FINS((CSL_APP_RCM_U_BASE + CSL_APP_RCM_IPCFGCLKGATE0), APP_RCM_IPCFGCLKGATE0_IPCFGCLKGATE0_APP_RTI, 0x0);

    TimerP_Params_init(&timerParams);
    timerParams.inputPreScaler = CONFIG_TIMER0_INPUT_PRE_SCALER;
    timerParams.inputClkHz     = CONFIG_TIMER0_INPUT_CLK_HZ;
    timerParams.periodInUsec   = CONFIG_TIMER0_USEC_PER_TICK;
    timerParams.oneshotMode    = 0;
    timerParams.enableOverflowInt = 1;
    TimerP_setup(gTimerBaseAddr[CONFIG_TIMER0], &timerParams);

    HwiP_Params_init(&timerHwiParams);
    timerHwiParams.intNum = 16 + CONFIG_TIMER0_INT_NUM;
    timerHwiParams.callback = TimerP_isr0;
    timerHwiParams.isPulse = 0;
    timerHwiParams.priority = 4;
    status = HwiP_construct(&gTimerHwiObj[CONFIG_TIMER0], &timerHwiParams);
    DebugP_assertNoLog(status==SystemP_SUCCESS);

}

void TimerP_deinit()
{
    TimerP_stop(gTimerBaseAddr[CONFIG_TIMER0]);
    HwiP_destruct(&gTimerHwiObj[CONFIG_TIMER0]);

}

#define BOOT_SECTION __attribute__((section(".text.boot")))

/* This function is called by _c_int00 */
void BOOT_SECTION __mpu_init() 
{
    MpuP_init();
}

void Dpl_init(void)
{
    /* initialize Hwi but keep interrupts disabled */
    HwiP_init();

    /* init debug log zones early */
    /* Debug log init */
    DebugP_logZoneEnable(DebugP_LOG_ZONE_ERROR);
    DebugP_logZoneEnable(DebugP_LOG_ZONE_WARN);

    /* initialize Clock */
    ClockP_init();

    TimerP_init();
    /* Enable interrupt handling */
    HwiP_enable();
}

void Dpl_deinit(void)
{
    ClockP_deinit();
    TimerP_deinit();
}
