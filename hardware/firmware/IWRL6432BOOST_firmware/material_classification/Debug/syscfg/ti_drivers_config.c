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

#include "ti_drivers_config.h"

/*
 * QSPI
 */


/* QSPI attributes */
static QSPI_Attrs gQspiAttrs[CONFIG_QSPI_NUM_INSTANCES] =
{
    {
        .baseAddr             = CSL_APP_CFG_QSPI_U_BASE,
        .memMapBaseAddr       = CSL_APP_QSPI_EXT_FLASH_U_BASE,
        .inputClkFreq         = 80000000U,
        .intrNum              = 29U,
        .intrEnable           = FALSE,
        .dmaEnable            = FALSE,
        .intrPriority         = 4U,
        .rxLines              = QSPI_RX_LINES_QUAD,
        .chipSelect           = QSPI_CS0,
        .csPol                = QSPI_CS_POL_ACTIVE_LOW,
        .dataDelay            = QSPI_DATA_DELAY_0,
        .frmFmt               = QSPI_FF_POL0_PHA0,
        .wrdLen               = 8,
        .baudRateDiv          = 0,
    },
};
/* QSPI objects - initialized by the driver */
static QSPI_Object gQspiObjects[CONFIG_QSPI_NUM_INSTANCES];
/* QSPI driver configuration */
QSPI_Config gQspiConfig[CONFIG_QSPI_NUM_INSTANCES] =
{
    {
        &gQspiAttrs[CONFIG_QSPI0],
        &gQspiObjects[CONFIG_QSPI0],
    },
};

uint32_t gQspiConfigNum = CONFIG_QSPI_NUM_INSTANCES;

/*
 * EDMA
 */
/* EDMA atrributes */
static EDMA_Attrs gEdmaAttrs[CONFIG_EDMA_NUM_INSTANCES] =
{
    {

        .baseAddr           = CSL_APP_TPCC_B_U_BASE,
        .compIntrNumber     = (16U + CSL_APPSS_INTR_APPSS_TPCC2_INTAGG),
        .intrAggEnableAddr  = CSL_APP_CTRL_U_BASE + CSL_APP_CTRL_APPSS_TPCC_B_INTAGG_MASK,
        .intrAggEnableMask  = 0x1FF & (~(2U << 0)),
        .intrAggStatusAddr  = CSL_APP_CTRL_U_BASE + CSL_APP_CTRL_APPSS_TPCC_B_INTAGG_STATUS,
        .intrAggClearMask   = (2U << 0),
        .initPrms           =
        {
            .regionId     = 0,
            .queNum       = 0,
            .initParamSet = FALSE,
            .ownResource    =
            {
                .qdmaCh      = 0xFFU,
                .dmaCh[0]    = 0xFFFFFFFFU,
                .dmaCh[1]    = 0xFFFFFFFFU,
                .tcc[0]      = 0xFFFFFFFFU,
                .tcc[1]      = 0xFFFFFFFFU,
                .paramSet[0] = 0xFFFFFFFFU,
                .paramSet[1] = 0xFFFFFFFFU,
                .paramSet[2] = 0xFFFFFFFFU,
                .paramSet[3] = 0xFFFFFFFFU,
            },
            .reservedDmaCh[0]    = 0x01U,
            .reservedDmaCh[1]    = 0x00U,
        },
    },
    {

        .baseAddr           = CSL_APP_TPCC_A_U_BASE,
        .compIntrNumber     = (16U + CSL_APPSS_INTR_APPSS_TPCC1_INTAGG),
        .intrAggEnableAddr  = CSL_APP_CTRL_U_BASE + CSL_APP_CTRL_APPSS_TPCC_A_INTAGG_MASK,
        .intrAggEnableMask  = 0x1FF & (~(2U << 0)),
        .intrAggStatusAddr  = CSL_APP_CTRL_U_BASE + CSL_APP_CTRL_APPSS_TPCC_A_INTAGG_STATUS,
        .intrAggClearMask   = (2U << 0),
        .initPrms           =
        {
            .regionId     = 0,
            .queNum       = 0,
            .initParamSet = FALSE,
            .ownResource    =
            {
                .qdmaCh      = 0xFFU,
                .dmaCh[0]    = 0xFFFFFFFFU,
                .dmaCh[1]    = 0xFFFFFFFFU,
                .tcc[0]      = 0xFFFFFFFFU,
                .tcc[1]      = 0xFFFFFFFFU,
                .paramSet[0] = 0xFFFFFFFFU,
                .paramSet[1] = 0xFFFFFFFFU,
                .paramSet[2] = 0xFFFFFFFFU,
                .paramSet[3] = 0xFFFFFFFFU,
            },
            .reservedDmaCh[0]    = 0x01U,
            .reservedDmaCh[1]    = 0x00U,
        },
    },
};

/* EDMA objects - initialized by the driver */
static EDMA_Object gEdmaObjects[CONFIG_EDMA_NUM_INSTANCES];
/* EDMA driver configuration */
EDMA_Config gEdmaConfig[CONFIG_EDMA_NUM_INSTANCES] =
{
    {
        &gEdmaAttrs[CONFIG_EDMA0],
        &gEdmaObjects[CONFIG_EDMA0],
    },
    {
        &gEdmaAttrs[CONFIG_EDMA1],
        &gEdmaObjects[CONFIG_EDMA1],
    },
};

uint32_t gEdmaConfigNum = CONFIG_EDMA_NUM_INSTANCES;

/*
 * HWA
 */
/* HWA atrributes */
HWA_Attrs gHwaAttrs[CONFIG_HWA_NUM_INSTANCES] =
{
    {
        .instanceNum                = 0U,
        .ctrlBaseAddr               = CSL_APP_HWA_CFG_U_BASE,
        .paramBaseAddr              = CSL_APP_HWA_PARAM_U_BASE,
        .ramBaseAddr                = CSL_APP_HWA_WINDOW_RAM_U_BASE,
        .numHwaParamSets            = SOC_HWA_NUM_PARAM_SETS,
        .intNumParamSet             = (16U + CSL_APPSS_INTR_HWASS_PARAMDONE_INT),
        .intNumDone                 = (16U + CSL_APPSS_INTR_HWASS_LOOP_INT),
        .numDmaChannels             = SOC_HWA_NUM_DMA_CHANNEL,
        .accelMemBaseAddr           = CSL_APP_HWA_DMA0_U_BASE,
        .accelMemSize               = SOC_HWA_MEM_SIZE,
        .isConcurrentAccessAllowed  = true,
        .isCompressionEnginePresent = true,
    },
};
/* HWA RAM atrributes */
HWA_RAMAttrs gHwaRamCfg[HWA_NUM_RAMS] =
{
    {CSL_APP_HWA_WINDOW_RAM_U_BASE, CSL_APP_HWA_WINDOW_RAM_U_SIZE},
    {CSL_APP_HWA_MC_PING_RAM_U_BASE, CSL_APP_HWA_MC_PING_RAM_U_SIZE},
    {CSL_APP_HWA_MC_PONG_RAM_U_BASE, CSL_APP_HWA_MC_PONG_RAM_U_SIZE}
};

/* HWA objects - initialized by the driver */
HWA_Object gHwaObject[CONFIG_HWA_NUM_INSTANCES];
/* HWA objects - storage for HWA driver object handles */
HWA_Object *gHwaObjectPtr[CONFIG_HWA_NUM_INSTANCES] = { NULL };
/* HWA objects count */
uint32_t gHwaConfigNum = CONFIG_HWA_NUM_INSTANCES;

/*
 * I2C
 */
/* I2C atrributes */
static I2C_HwAttrs gI2cHwAttrs[CONFIG_I2C_NUM_INSTANCES] =
{
    {
        .baseAddr       = CSL_APP_I2C_U_BASE,
        .intNum         = 35,
        .eventId        = 0,
        .funcClk        = 40000000U,
        .enableIntr     = 1,
        .ownTargetAddr   = 0x1C,
    },
};
/* I2C objects - initialized by the driver */
static I2C_Object gI2cObjects[CONFIG_I2C_NUM_INSTANCES];
/* I2C driver configuration */
I2C_Config gI2cConfig[CONFIG_I2C_NUM_INSTANCES] =
{
    {
        .object = &gI2cObjects[CONFIG_I2C0],
        .hwAttrs = &gI2cHwAttrs[CONFIG_I2C0]
    },
};

uint32_t gI2cConfigNum = CONFIG_I2C_NUM_INSTANCES;

/*
 * Copyright (c) 2018-2020, Texas Instruments Incorporated - http://www.ti.com
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * *  Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * *  Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * *  Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 */

 

/*
 *  =============================== Power ===============================
 */
#include <drivers/power.h>
#include <drivers/power_xwrLx4xx.h>
#include <drivers/prcm.h>


extern void Power_initPolicy(void);
extern void Power_sleepPolicy(unsigned long long sleepTimeus);
extern void power_LPDSentryhook(void);
extern void power_LPDSresumehook(void);
extern void power_idle3entryhook(void);
extern void power_idle3resumehook(void);
Power_ParkInfo parkInfo[];


/*
 *  This structure defines the configuration for the Power Manager.
 */
const Power_ConfigV1 Power_config = {
    .policyInitFxn             = Power_initPolicy,
    .policyFxn                 = Power_sleepPolicy,
    .enterLPDSHookFxn          = power_LPDSentryhook,
    .resumeLPDSHookFxn         = power_LPDSresumehook,
    .enteridle3HookFxn          = power_idle3entryhook,
    .resumeidle3HookFxn         = power_idle3resumehook,
    .enablePolicy                   = false,
    .enableSleepCounterWakeupLPDS   = true,
    .enableUARTWakeupLPDS           = false,
    .enableSPICSWakeupLPDS          = false,
    .enableRTCWakeupLPDS            = false,
    .enableFRCWakeupLPDS            = false,
    .enableGPIOSyncIOWakeupLPDS           = false,
    .wakeupSyncIOEdgeLPDS           = PRCM_LPDS_FALL_EDGE,
    .LPDSThreshold                   = 10000,
    .totalLatencyForLPDS                 = 2000,
    .sleepThreshold                   = 99999999,
    .totalLatencyForSleep                 = 99999999,
    .idleThreshold                   = 2000,
    .totalLatencyForIdle                 = 1000,
    .ramRetentionMaskLPDS           = PRCM_APP_PD_SRAM_CLUSTER_1|PRCM_APP_PD_SRAM_CLUSTER_2|PRCM_APP_PD_SRAM_CLUSTER_3|PRCM_APP_PD_SRAM_CLUSTER_4|PRCM_APP_PD_SRAM_CLUSTER_5|PRCM_APP_PD_SRAM_CLUSTER_6|PRCM_FEC_PD_SRAM_CLUSTER_1,
    .pinParkDefs                    = parkInfo,
    .numPins                        = 24
};

Power_ParkInfo parkInfo[] = {
/*        PIN                    PARK STATE              Pin Alias
   -----------------  ------------------------------     ---------------*/

   {POWER_PIN_PAD_AA, POWER_PARK},   /*PIN_PAD_AA*/

   {POWER_PIN_PAD_AB, POWER_PARK},   /*PIN_PAD_AB*/

   {POWER_PIN_PAD_AC, POWER_PARK},   /*PIN_PAD_AC*/

   {POWER_PIN_PAD_AD, POWER_PARK},   /*PIN_PAD_AD*/

   {POWER_PIN_PAD_AE, POWER_PARK},   /*PIN_PAD_AE*/

   {POWER_PIN_PAD_AF, POWER_PARK},   /*PIN_PAD_AF*/

   {POWER_PIN_PAD_AG, POWER_PARK},   /*PIN_PAD_AG*/

   {POWER_PIN_PAD_AH, POWER_PARK},   /*PIN_PAD_AH*/

   {POWER_PIN_PAD_AI, POWER_PARK},   /*PIN_PAD_AI*/

   {POWER_PIN_PAD_AJ, POWER_PARK},   /*PIN_PAD_AJ*/

   {POWER_PIN_PAD_AK, POWER_PARK},   /*PIN_PAD_AK*/

   {POWER_PIN_PAD_AL, POWER_PARK},   /*PIN_PAD_AL*/

   {POWER_PIN_PAD_AM, POWER_PARK},   /*PIN_PAD_AM*/

   {POWER_PIN_PAD_AN, POWER_PARK},   /*PIN_PAD_AN*/

   {POWER_PIN_PAD_AO, POWER_PARK},   /*PIN_PAD_AO*/

   {POWER_PIN_PAD_AP, POWER_PARK},   /*PIN_PAD_AP*/

   {POWER_PIN_PAD_AQ, POWER_DONT_PARK},   /*PIN_PAD_AQ*/

   {POWER_PIN_PAD_AR, POWER_DONT_PARK},   /*PIN_PAD_AR*/

   {POWER_PIN_PAD_AS, POWER_DONT_PARK},   /*PIN_PAD_AS*/

   {POWER_PIN_PAD_AT, POWER_DONT_PARK},   /*PIN_PAD_AT*/

   {POWER_PIN_PAD_AU, POWER_PARK},   /*PIN_PAD_AU*/

   {POWER_PIN_PAD_AV, POWER_DONT_PARK},   /*PIN_PAD_AV*/

   {POWER_PIN_PAD_AW, POWER_PARK},   /*PIN_PAD_AW*/

   {POWER_PIN_PAD_AX, POWER_PARK},   /*PIN_PAD_AX*/

};

/*
 * UART
 */
#include "drivers/soc.h"

/* UART atrributes */
static UART_Attrs gUartAttrs[CONFIG_UART_NUM_INSTANCES] =
{
    {
        .baseAddr           = CSL_APP_UART1_U_BASE,
        .inputClkFreq       = 40000000U,
    },
};
/* UART objects - initialized by the driver */
static UART_Object gUartObjects[CONFIG_UART_NUM_INSTANCES];
/* UART driver configuration */
UART_Config gUartConfig[CONFIG_UART_NUM_INSTANCES] =
{
    {
        &gUartAttrs[CONFIG_UART0],
        &gUartObjects[CONFIG_UART0],
    },
};

uint32_t gUartConfigNum = CONFIG_UART_NUM_INSTANCES;

void Drivers_uartInit(void)
{
    uint32_t i;
    for (i=0; i<CONFIG_UART_NUM_INSTANCES; i++)
    {
        SOC_RcmPeripheralId periphID;
        if(gUartAttrs[i].baseAddr == CSL_APP_UART0_U_BASE) {
            periphID = SOC_RcmPeripheralId_APPSS_UART0;
        } else if (gUartAttrs[i].baseAddr == CSL_APP_UART1_U_BASE) {
            periphID = SOC_RcmPeripheralId_APPSS_UART1;
        } else {
            continue;
        }
        gUartAttrs[i].inputClkFreq = SOC_rcmGetPeripheralClock(periphID);
    }
    UART_init();
}


#define TOP_PRCM_CLK_CTRL_REG1_LDO_CLKTOP_ADDR 0x5A040520
void Pinmux_init();
void PowerClock_init(void);
void PowerClock_deinit(void);

/*
 * Common Functions
 */
extern uint8_t SOC_getEfusePgVersion(void);
void System_init(void)
{
    uint8_t pg_version;
    /* DPL init sets up address transalation unit, on some CPUs this is needed
     * to access SCICLIENT services, hence this needs to happen first
     */
    Dpl_init();
    PowerClock_init();

    /* Errata ANA-52: Slicer LDO TLOAD to be disabled to save unnecessary power burnout after oscillator is enabled */
    pg_version = SOC_getEfusePgVersion();
    if(pg_version==1){
        volatile int* prcmldoaddr = (volatile int*)TOP_PRCM_CLK_CTRL_REG1_LDO_CLKTOP_ADDR;
        *prcmldoaddr = (*prcmldoaddr) & (~(0xE000));
        *prcmldoaddr = (*prcmldoaddr) | (0x2000);
    }

    /* Now we can do pinmux */
    Pinmux_init();
    /* finally we initialize all peripheral drivers */
    QSPI_init();
    EDMA_init();
    HWA_init();
    I2C_init();
    Power_init();

    Drivers_uartInit();
}

void System_deinit(void)
{
    QSPI_deinit();
    EDMA_deinit();
    HWA_deinit();
    I2C_deinit();
    UART_deinit();
    PowerClock_deinit();
    Dpl_deinit();
}
