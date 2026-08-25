/*
 * Copyright (C) 2022-24 Texas Instruments Incorporated
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 *   Redistributions of source code must retain the above copyright
 *   notice, this list of conditions and the following disclaimer.
 *
 *   Redistributions in binary form must reproduce the above copyright
 *   notice, this list of conditions and the following disclaimer in the
 *   documentation and/or other materials provided with the
 *   distribution.
 *
 *   Neither the name of Texas Instruments Incorporated nor the names of
 *   its contributors may be used to endorse or promote products derived
 *   from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
/**************************************************************************
 *************************** Include Files ********************************
 **************************************************************************/

/* Standard Include Files. */
#include <stdint.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <assert.h>

/* MCU Plus Include Files. */
#include <kernel/dpl/SemaphoreP.h>
#include <kernel/dpl/CacheP.h>
#include <kernel/dpl/ClockP.h>
#include <kernel/dpl/DebugP.h>
#include <kernel/dpl/HwiP.h>
#include <kernel/dpl/AddrTranslateP.h>

#include "FreeRTOS.h"
#include "task.h"

/* mmwave SDK files */
#include <datapath/dpedma/v0/dpedmahwa.h>
#include <datapath/dpedma/v0/dpedma.h>
#include <datapath/dpu/rangeproc/v0/rangeprochwa.h>
#include <datapath/dpu/rangeproc/v0/rangeprochwa_internal.h>
#include <datapath/dpu/dopplerproc/v0/dopplerprochwa.h>
#include <datapath/dpu/aoa2dproc/v0/aoa2dproc.h>

#include <control/mmwave/mmwave.h>
#include <drivers/edma.h>
#include <drivers/uart.h>
#include <drivers/i2c.h>
#include <drivers/hw_include/cslr_adcbuf.h>

#include <board/ina.h>

#include <utils/mathutils/mathutils.h>
#include "mmw_cli.h"
#include <drivers/mcspi.h>

#include "mmw_res.h"
#include "mmwave_demo.h"
#include "calibrations/mmw_flash_cal.h"
#include <alg/caponBeamforming2D/caponBeamforming2D.h>


#include "ti_drivers_config.h"
#include "ti_drivers_open_close.h"
#include "ti_board_open_close.h"
#include "ti_board_config.h"
#include <FreeRTOS.h>
#include <task.h>
#include <semphr.h>
#include "drivers/power.h"
#include <mmwavelink/include/rl_device.h>
#include <mmwavelink/include/rl_sensor.h>
#include <drivers/prcm.h>
#include <drivers/hw_include/cslr_soc.h>

#include "dpc/dpc.h"
#include "calibrations/range_phase_bias_measurement.h"
#include "utils/mmw_demo_utils.h"
#include "calibrations/factory_cal.h"
#include "mmwave_control/monitors.h"
#include "power_management/power_management.h"

/* Enable Continuous wave mode */
#define CONTINUOUS_WAVE_MODE_ENABLE   0

#define DPU_DOAPROC_6432_1432_BOARD 0
#define DPU_DOAPROC_ISK_BOARD 1
#define DPC_OBJDET_DPIF_RADARCUBE_FORMAT_6 6
#define DPC_DPU_DPIF_DETMATRIX_FORMAT_2 2

#define DPC_OBJDET_HWA_DOPPLER_WINDOW_RAM_OFFSET 128
//#define DPC_OBJDET_HWA_VECTOR_RAM_OFFSET 0

#define FRAME_REF_TIMER_CLOCK_MHZ  40

// Time to transfer single Byte of data obtained by measuring time for various data size.
#define TIME_TO_SEND_1BYTE_DATA_WITH_BAUDRATE_115200_us  95  
#define TIME_TO_SEND_1BYTE_DATA_WITH_BAUDRATE_1250000_us  10   


uint8_t                 pgVersion;
uint8_t                 rxData[16];
uint8_t                 txData[16];
I2C_Transaction         i2cTransaction;

MmwDemo_MSS_MCB gMmwMssMCB = {0};

/* Default antenna geometry - XWR6432 EVM */
MmwDemo_antennaGeometryCfg gDefaultAntGeometry = {.ant = {{0,0}, {1,1}, {0,2}, {0,1}, {1,2}, {0,3}}};

//Interrupt object for Sensor Stop
HwiP_Object gHwiSensorStopHwiObject;

/*! L3 RAM buffer for object detection DPC */
#define L3_MEM_SIZE (0x40000 + 160*1024)
uint8_t gMmwL3[L3_MEM_SIZE]  __attribute((section(".l3")));

/*! Local RAM buffer for object detection DPC */
#define MMWDEMO_OBJDET_CORE_LOCAL_MEM_SIZE ((8U+6U+4U+2U+8U) * 1024U)
uint8_t gMmwCoreLocMem[MMWDEMO_OBJDET_CORE_LOCAL_MEM_SIZE];

HWA_Handle hwaHandle;

MMWave_temperatureStats  tempStats;

extern void Mmwave_populateDefaultCalibrationCfg (MMWave_CalibrationCfg* ptrCalibrationCfg);

extern void MMWave_getTemperatureReport (MMWave_temperatureStats* ptrTempStats);

int32_t mmwDemo_mmWaveInit(bool iswarmstrt);
#if (ENABLE_MONITORS==1)
/*API to get Results of RF Monitors*/
extern void mmwDemo_GetMonRes(void);
#endif
// Radar Power Management Framework
// Priority of Power task
#define POWER_TASK_PRI  (2u)
// Stack for Power task
#define POWER_TASK_SIZE (1024u)
#define LOW_PWR_MODE_DISABLE (0)
#define LOW_PWR_MODE_ENABLE (1)
#define LOW_PWR_TEST_MODE (2)

#define MMWINITTASK_PRI  (5u)
#define MMWINIT_TASK_SIZE (1024u)
#define CLI_REMOVAL 1

StaticTask_t gmmwinitTaskObj;
TaskHandle_t gmmwinitTask;
extern void mmwreinitTask(void *args);
StackType_t gmmwinitTaskStack[MMWINIT_TASK_SIZE] __attribute__((aligned(32)));
StaticSemaphore_t gmmwinitObj;
SemaphoreHandle_t gmmwinit;

StackType_t gPowerTaskStack[POWER_TASK_SIZE] __attribute__((aligned(32)));
// Power task objects
StaticTask_t gPowerTaskObj;
TaskHandle_t gPowerTask;
// Power task semaphore objects
StaticSemaphore_t gPowerSemObj;
SemaphoreHandle_t gPowerSem;

// LED config
uint32_t gpioBaseAddrLed, pinNumLed;

//For Sensor Stop
uint32_t sensorStop = 0;
extern int8_t isSensorStarted;
extern float gSocClk; 

// For freeing the channels after Sensor Stop
void mmwDemo_freeDmaChannels(EDMA_Handle edmaHandle);

void MmwDemo_stopSensor(void);

extern volatile unsigned long long demoStartTime;
volatile unsigned long long demoEndTime, slpTimeus,lpdsLatency;
extern TaskHandle_t gDpcTask;
extern TaskHandle_t gAdcFileTask;
// char bootRst[6][15] = {"PORZ", "Warm Reset", "Deep Sleep", "Soft Reset", "STC_WARM", "STC_PORZ"};
double demoTimeus,frmPrdus;

/**
 *  @b Description
 *  @n
 *      Send assert information through CLI.
 */
void _MmwDemo_debugAssert(int32_t expression, const char *file, int32_t line)
{
    if (!expression) {
        CLI_write ("Exception: %s, line %d.\r\n",file,line);
    }
}

/**
*  @b Description
*  @n
*        Function configuring and executing DPC
*/
void mmwDemo_dpcTask()
{
    
    DPC_Config();
    printf("DPC CONFIG FINISHED !\n");

    DPC_Execute();

    /* Never return for this task. */
    SemaphoreP_pend(&gMmwMssMCB.TestSemHandle, SystemP_WAIT_FOREVER);
}

/**
 *  @b Description
 *  @n
 *     UART write wrapper function
 *
 * @param[in]   handle          UART handle
 * @param[in]   payload         Pointer to payload data
 * @param[in]   payloadLength   Payload length in bytes
 *
 *  @retval
 *      Not Applicable.
 */
void mmw_UartWrite (UART_Handle handle,
                    uint8_t *payload,
                    uint32_t payloadLength)
{
    UART_Transaction trans;

    UART_Transaction_init(&trans);

    trans.buf   = payload;
    trans.count = payloadLength;

    UART_write(handle, &trans);
}

void mmw_UartWrite_float (UART_Handle handle,
                    float *payload,
                    uint32_t payloadLength)
{
    UART_Transaction trans;

    UART_Transaction_init(&trans);

    trans.buf   = payload;
    trans.count = payloadLength;

    UART_write(handle, &trans);
}

void mmwDemo_INAMeasNull(I2C_Handle i2cHandle, uint16_t *ptrPwrMeasured)
{
    ptrPwrMeasured[0] = (uint16_t)0xFFFF;
    ptrPwrMeasured[1] = (uint16_t)0xFFFF;
    ptrPwrMeasured[2] = (uint16_t)0xFFFF;
    ptrPwrMeasured[3] = (uint16_t)0xFFFF;
}

/** @brief Transmits detection data over UART
*
*    The following data is transmitted:
*    1. Header (size = 32bytes), including "Magic word", (size = 8 bytes)
*       and including the number of TLV items
*    TLV Items:
*    2. If pointCloud flag is 1 or 2, DPIF_PointCloudCartesian structure containing
*       X,Y,Z location and velocity for detected objects,
*       size = sizeof(DPIF_PointCloudCartesian) * number of detected objects
*    3. If pointCloud flag is 1, DPIF_PointCloudSideInfo structure containing SNR
*       and noise for detected objects,
*       size = sizeof(DPIF_PointCloudCartesian) * number of detected objects
*    4. If rangeProfile flag is set,  rangeProfile,
*       size = number of range bins * sizeof(uint32_t)
*    5. noiseProfile flag is set is not used.
*    6. If rangeAzimuthHeatMap flag is set, sends range/azimuth heatmap, size = number of range bins *
*       number of azimuth bins * sizeof(uint32_t)
*    7. rangeDopplerHeatMap flag is not used
*    8. If statsInfo flag is set, the stats information, timing, temperature and power
*/
void mmwDemo_TransmitProcessedOutputTask()
{
    UART_Handle uartHandle = gUartHandle[0];
    I2C_Handle  i2cHandle = gI2cHandle[CONFIG_I2C0];
    DPC_ObjectDetection_ExecuteResult *result = &gMmwMssMCB.dpcResult;
    //MmwDemo_output_message_stats      *timingInfo
    MmwDemo_output_message_header header;
    CLI_GuiMonSel   *pGuiMonSel;
    uint32_t tlvIdx = 0;
    //uint32_t i;
    uint32_t numPaddingBytes;
    uint32_t packetLen;
    uint8_t padding[MMWDEMO_OUTPUT_MSG_SEGMENT_LEN];
    MmwDemo_output_message_tl   tl[MMWDEMO_OUTPUT_ALL_MSG_MAX];
    uint32_t txUartus = 0;
    uint32_t uartTxStartTime;
    uint32_t timeElapsedus;
    uint32_t framePeriodicityus; 
    uint32_t timeRemainUart;
    uint32_t startCycle;
    /* Get Gui Monitor configuration */
    pGuiMonSel = &gMmwMssMCB.guiMonSel; //&subFrameCfg->guiMonSel;

    /* Send signal to CLI task that this task is ready */
    SemaphoreP_post(&gMmwMssMCB.uartTaskConfigDoneSemHandle);

    while(true)
    {
        SemaphoreP_pend(&gMmwMssMCB.tlvSemHandle, SystemP_WAIT_FOREVER);
        startCycle = CycleCounterP_getCount32();
        tlvIdx = 0;

        /* Clear message header */
        memset((void *)&header, 0, sizeof(MmwDemo_output_message_header));
        /* Header: */
        header.platform =  0xA6432;
        header.magicWord[0] = 0x0102;
        header.magicWord[1] = 0x0304;
        header.magicWord[2] = 0x0506;
        header.magicWord[3] = 0x0708;
        header.numDetectedObj = result->numObjOut;
        header.version =    MMWAVE_SDK_VERSION_BUILD |   //DEBUG_VERSION
                            (MMWAVE_SDK_VERSION_BUGFIX << 8) |
                            (MMWAVE_SDK_VERSION_MINOR << 16) |
                            (MMWAVE_SDK_VERSION_MAJOR << 24);


        packetLen = sizeof(MmwDemo_output_message_header);

        /* Capon Spectrum 3D Info */
        if ((pGuiMonSel->CaponSpectrum3DHeatmap==1) && (result->caponBf3DHeatmap != NULL)) {
            tl[tlvIdx].type = INTRAMAP_OUTPUT_EXT_CAPON_SPECTRUM_3D_HEATMAP;
            tl[tlvIdx].length = 10*gMmwMssMCB.caponSpectrumLength; // in bytes so that is okay
            packetLen += sizeof(MmwDemo_output_message_tl) + tl[tlvIdx].length;
            tlvIdx++;
        }

        if ((pGuiMonSel->pointCloud == 1) && (result->numObjOut > 0))
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_MSG_DETECTED_POINTS;
            tl[tlvIdx].length = sizeof(DPIF_PointCloudCartesian) * result->numObjOut;
            packetLen += sizeof(MmwDemo_output_message_tl) + tl[tlvIdx].length;
            tlvIdx++;
        }

        /* Side info */
        if ((pGuiMonSel->pointCloud == 1) && result->numObjOut > 0)
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_MSG_DETECTED_POINTS_SIDE_INFO;
            tl[tlvIdx].length = sizeof(DPIF_PointCloudSideInfo) * result->numObjOut;
            packetLen += sizeof(MmwDemo_output_message_tl) + tl[tlvIdx].length;
            tlvIdx++;
        }

        /* Point Cloud Compressed format */
        if ((pGuiMonSel->pointCloud == 2) && (result->numObjOut > 0))
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_EXT_MSG_DETECTED_POINTS;
            tl[tlvIdx].length = sizeof(MmwDemo_output_message_point_unit) +
                                sizeof(MmwDemo_output_message_UARTpoint) * result->numObjOut;
            packetLen += sizeof(MmwDemo_output_message_tl) + tl[tlvIdx].length;
            tlvIdx++;
        }

        /* Range Profile (Major motion) */
        if ((pGuiMonSel->rangeProfile & 0x1) && (gMmwMssMCB.rangeProfile != NULL))
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_EXT_MSG_RANGE_PROFILE_MAJOR;
            tl[tlvIdx].length = sizeof(uint32_t) * gMmwMssMCB.numRangeBins;
            packetLen += sizeof(MmwDemo_output_message_tl) + tl[tlvIdx].length;
            tlvIdx++;
        }
        /* Range Profile (Minor motion) */
        if ((pGuiMonSel->rangeProfile & 0x2) && (gMmwMssMCB.rangeProfile != NULL))
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_EXT_MSG_RANGE_PROFILE_MINOR;
            tl[tlvIdx].length = sizeof(uint32_t) * gMmwMssMCB.numRangeBins;
            packetLen += sizeof(MmwDemo_output_message_tl) + tl[tlvIdx].length;
            tlvIdx++;
        }

        /* Range-Azimuth Heatmap (Major motion) */
        if ((pGuiMonSel->rangeAzimuthHeatMap & 0x1) && (result->rngAzHeatMap[0] != NULL))
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_EXT_MSG_RANGE_AZIMUT_HEAT_MAP_MAJOR;
            tl[tlvIdx].length = gMmwMssMCB.numRangeBins * gMmwMssMCB.sigProcChainCfg.azimuthFftSize * sizeof(uint32_t);
            packetLen += sizeof(MmwDemo_output_message_tl) +  tl[tlvIdx].length;
            tlvIdx++;
        }
        /* Range-Azimuth Heatmap (Minor motion) */
        if ((pGuiMonSel->rangeAzimuthHeatMap & 0x2) && (result->rngAzHeatMap[1] != NULL))
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_EXT_MSG_RANGE_AZIMUT_HEAT_MAP_MINOR;
            tl[tlvIdx].length = gMmwMssMCB.numRangeBins * gMmwMssMCB.sigProcChainCfg.azimuthFftSize * sizeof(uint32_t);
            packetLen += sizeof(MmwDemo_output_message_tl) +  tl[tlvIdx].length;
            tlvIdx++;
        }
        /* Range-Doppler Heatmap */
        if ((pGuiMonSel->rangeDopplerHeatMap) && (result->rngDopplerHeatMap != NULL))
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_MSG_RANGE_DOPPLER_HEAT_MAP;
            tl[tlvIdx].length = gMmwMssMCB.numRangeBins * gMmwMssMCB.numDopplerBins * sizeof(uint32_t);
            packetLen += sizeof(MmwDemo_output_message_tl) +  tl[tlvIdx].length;
            tlvIdx++;
        }

        if (pGuiMonSel->statsInfo)
        {
            memcpy((void*)gMmwMssMCB.outStats.tempReading, &tempStats.tempValue, (4 * sizeof(int16_t)));
            
            #ifdef INA228
            if(gMmwMssMCB.spiADCStream != 1)
            {
                mmwDemo_PowerMeasurement(i2cHandle, &gMmwMssMCB.outStats.powerMeasured[0]);
            }
            else
            {
                mmwDemo_INAMeasNull(i2cHandle, &gMmwMssMCB.outStats.powerMeasured[0]);
            }
            #else
            mmwDemo_INAMeasNull(i2cHandle, &gMmwMssMCB.outStats.powerMeasured[0]);
            #endif
            tl[tlvIdx].type = MMWDEMO_OUTPUT_EXT_MSG_STATS;
            tl[tlvIdx].length = sizeof(MmwDemo_output_message_stats);
            packetLen += sizeof(MmwDemo_output_message_tl) +  tl[tlvIdx].length;
            tlvIdx++;
        }


        if (pGuiMonSel->adcSamples)
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_EXT_MSG_ADC_SAMPLES;
            tl[tlvIdx].length = gMmwMssMCB.numRxAntennas * gMmwMssMCB.numTxAntennas * gMmwMssMCB.profileComCfg.h_NumOfAdcSamples * sizeof(int16_t);
            packetLen += sizeof(MmwDemo_output_message_tl) +  tl[tlvIdx].length;
            tlvIdx++;
        }


        if (gMmwMssMCB.measureRxChannelBiasCliCfg.enabled)
        {
            tl[tlvIdx].type = MMWDEMO_OUTPUT_EXT_MSG_RX_CHAN_COMPENSATION_INFO;
            tl[tlvIdx].length = sizeof(DPIF_compRxChannelBiasFloatCfg);
            packetLen += sizeof(MmwDemo_output_message_tl) + tl[tlvIdx].length;
            tlvIdx++;
        }

        /* Fill header */
        header.numTLVs = tlvIdx;
        /* Round up packet length to multiple of MMWDEMO_OUTPUT_MSG_SEGMENT_LEN */
        header.totalPacketLen = MMWDEMO_OUTPUT_MSG_SEGMENT_LEN *
                ((packetLen + (MMWDEMO_OUTPUT_MSG_SEGMENT_LEN-1))/MMWDEMO_OUTPUT_MSG_SEGMENT_LEN);
        header.timeCpuCycles =  0; //TODO: Populate with actual time
        header.frameNumber = gMmwMssMCB.stats.frameStartIntCounter; 
        header.subFrameNumber = -1;
        
        /* Check if there is enough time for all TLVs*/
        uartTxStartTime = Cycleprofiler_getTimeStamp();
        timeElapsedus = (gMmwMssMCB.outStats.interFrameProcessingTime + gMmwMssMCB.stats.chirpingTime_us + ((uartTxStartTime - gMmwMssMCB.stats.interFrameEndTimeStamp)/FRAME_REF_TIMER_CLOCK_MHZ));
        framePeriodicityus = (gMmwMssMCB.frameCfg.w_FramePeriodicity/gSocClk)*1000000;
        if(gUartParams[0].baudRate == 115200)
        {
           txUartus  = header.totalPacketLen * TIME_TO_SEND_1BYTE_DATA_WITH_BAUDRATE_115200_us;
        }
#ifdef  ENABLE_UART_HIGH_BAUD_RATE_DYNAMIC_CFG
        else if(gUartParams[0].baudRate == 1250000)
        {
            txUartus = header.totalPacketLen * TIME_TO_SEND_1BYTE_DATA_WITH_BAUDRATE_1250000_us;
        }
#endif
        timeRemainUart = framePeriodicityus - timeElapsedus;
        if(gMmwMssMCB.lowPowerMode == LOW_PWR_MODE_ENABLE)
        {   
            // Idle power mode has least threshold of all power modes hence considering 
            uint32_t idleThreshold = Power_getThresholds(POWER_IDLE);
            timeRemainUart = timeRemainUart - idleThreshold;
        }
              
        if(txUartus >= timeRemainUart)
        {
             CLI_write ("\r\n Warning: Frame Time is not enough to transfer all the configured TLVs!!! \r\n");
        }
        else
        {
            if(tlvIdx != 0)
            {
                mmw_UartWrite (uartHandle, (uint8_t*)&header, sizeof(MmwDemo_output_message_header));
                tlvIdx = 0;
            }

            if ((pGuiMonSel->CaponSpectrum3DHeatmap == 1) && (result->caponBf3DHeatmap != NULL)) {
                mmw_UartWrite (uartHandle,
                              (uint8_t*)&tl[tlvIdx],
                              sizeof(MmwDemo_output_message_tl));

                /*Send array of objects */
                mmw_UartWrite_float(uartHandle,
                                    (float*) gMmwMssMCB.caponSpectrum3DHeatmap,
                                    //(float*)result->caponBf3DHeatmap,
                                    10*gMmwMssMCB.caponSpectrumLength);
                tlvIdx++;
            }
            /* Send detected Objects */
            if ((pGuiMonSel->pointCloud == 1) && (result->numObjOut > 0))
            {
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));

                /*Send array of objects */
                mmw_UartWrite (uartHandle, (uint8_t*)result->objOut,
                                sizeof(DPIF_PointCloudCartesian) * result->numObjOut);
                tlvIdx++;
            }

            /* Send detected Objects Side Info */
            if ((pGuiMonSel->pointCloud == 1) && (result->numObjOut > 0))
            {
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));

                /*Send array of objects */
                mmw_UartWrite (uartHandle, (uint8_t*)result->objOutSideInfo,
                                sizeof(DPIF_PointCloudSideInfo) * result->numObjOut);
                tlvIdx++;
            }

            /* Send Point Cloud Compressed format */
            if ((pGuiMonSel->pointCloud == 2) && (result->numObjOut > 0))
            {
                /*Send point cloud */
                gMmwMssMCB.pointCloudToUart.header = tl[tlvIdx];
                mmw_UartWrite (uartHandle, (uint8_t*)&gMmwMssMCB.pointCloudToUart,
                            sizeof(MmwDemo_output_message_tl) + tl[tlvIdx].length);
                tlvIdx++;
            }

            /* Send Range profile (Major mode) */
            if ((pGuiMonSel->rangeProfile & 0x1) && (gMmwMssMCB.rangeProfile != NULL))
            {
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));

                mmw_UartWrite (uartHandle,
                                (uint8_t*)gMmwMssMCB.rangeProfile,
                                (sizeof(uint32_t)*(mathUtils_pow2roundup(gMmwMssMCB.profileComCfg.h_NumOfAdcSamples)/2)));
                tlvIdx++;
            }
            /* Send Range profile (Minor mode) */
            if ((pGuiMonSel->rangeProfile & 0x2) && (gMmwMssMCB.rangeProfile != NULL))
            {
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));

                mmw_UartWrite (uartHandle,
                                (uint8_t*)gMmwMssMCB.rangeProfile,
                                (sizeof(uint32_t)*(mathUtils_pow2roundup(gMmwMssMCB.profileComCfg.h_NumOfAdcSamples)/2)));
                tlvIdx++;
            }

            /* Send Range-Azimuth Heatmap (Major motion) */
            if ((pGuiMonSel->rangeAzimuthHeatMap & 0x1) && (result->rngAzHeatMap[0] != NULL))
            {
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));

                mmw_UartWrite (uartHandle,
                        (uint8_t *) result->rngAzHeatMap[0],
                        (gMmwMssMCB.numRangeBins * gMmwMssMCB.sigProcChainCfg.azimuthFftSize * sizeof(uint32_t)));

                tlvIdx++;
            }
            /* Send Range-Azimuth Heatmap (Minor motion) */
            if ((pGuiMonSel->rangeAzimuthHeatMap & 0x2) && (result->rngAzHeatMap[1] != NULL))
            {
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));

                mmw_UartWrite (uartHandle,
                        (uint8_t *) result->rngAzHeatMap[1],
                        (gMmwMssMCB.numRangeBins * gMmwMssMCB.sigProcChainCfg.azimuthFftSize * sizeof(uint32_t)));

                tlvIdx++;
            }
            /* Send Range-Doppler Heatmap */
            if ((pGuiMonSel->rangeDopplerHeatMap) && (result->rngDopplerHeatMap != NULL))
            {
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));

                {
                    int ii;
                    for (ii=0; ii<gMmwMssMCB.numRangeBins; ii++)
                    {
                        mmw_UartWrite (uartHandle,
                                (uint8_t *) &result->rngDopplerHeatMap[ii*gMmwMssMCB.numDopplerBins],
                                gMmwMssMCB.numDopplerBins * sizeof(uint32_t));
                    }
                }

                tlvIdx++;
            }

            /* Send stats information (interframe processing time and uart transfer time) */
            if (pGuiMonSel->statsInfo)
            {
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));

                mmw_UartWrite (uartHandle,
                            (uint8_t*) &gMmwMssMCB.outStats,
                            tl[tlvIdx].length);
                tlvIdx++;
            }

            /* Send ADC samples of last chirp pair in the frame */
            if (pGuiMonSel->adcSamples)
            {
                CSL_app_hwa_adcbuf_ctrlRegs *ptrAdcBufCtrlRegs = (CSL_app_hwa_adcbuf_ctrlRegs *)CSL_APP_HWA_ADCBUF_CTRL_U_BASE;

                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));

                if (gMmwMssMCB.numTxAntennas == 2)
                {
                    /* Set view to ADC ping buffer */
                    CSL_FINS(ptrAdcBufCtrlRegs->ADCBUFCFG1, APP_HWA_ADCBUF_CTRL_ADCBUFCFG1_ADCBUFCFG1_ADCBUFPIPOOVRCNT, 1);

                    mmw_UartWrite (uartHandle,
                                (uint8_t*) CSL_APP_HWA_ADCBUF_RD_U_BASE,
                                tl[tlvIdx].length/2);

                    /* Set view to ADC pong buffer */
                    CSL_FINS(ptrAdcBufCtrlRegs->ADCBUFCFG1, APP_HWA_ADCBUF_CTRL_ADCBUFCFG1_ADCBUFCFG1_ADCBUFPIPOOVRCNT, 0);

                    mmw_UartWrite (uartHandle,
                                (uint8_t*) CSL_APP_HWA_ADCBUF_RD_U_BASE,
                                tl[tlvIdx].length/2);
                }
                else
                {
                    /* Only one Tx antenna from ping buffer */
                    /* Set view to ADC ping buffer */
                    CSL_FINS(ptrAdcBufCtrlRegs->ADCBUFCFG1, APP_HWA_ADCBUF_CTRL_ADCBUFCFG1_ADCBUFCFG1_ADCBUFPIPOOVRCNT, 1);

                    mmw_UartWrite (uartHandle,
                                (uint8_t*) CSL_APP_HWA_ADCBUF_RD_U_BASE,
                                tl[tlvIdx].length);

                    /* Set view to ADC pong buffer */
                    CSL_FINS(ptrAdcBufCtrlRegs->ADCBUFCFG1, APP_HWA_ADCBUF_CTRL_ADCBUFCFG1_ADCBUFCFG1_ADCBUFPIPOOVRCNT, 0);
                }
                tlvIdx++;

            }


            /* Send Rx Channel compensation coefficients */
            if (gMmwMssMCB.measureRxChannelBiasCliCfg.enabled)
            {
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&tl[tlvIdx],
                                sizeof(MmwDemo_output_message_tl));
                mmw_UartWrite (uartHandle,
                                (uint8_t*)&gMmwMssMCB.compRxChannelBiasCfgMeasureOut,
                                tl[tlvIdx].length);
                tlvIdx++;
            }

            if(tlvIdx != 0)
            {
                /* Send padding bytes */
                numPaddingBytes = MMWDEMO_OUTPUT_MSG_SEGMENT_LEN - (packetLen & (MMWDEMO_OUTPUT_MSG_SEGMENT_LEN-1));
                if (numPaddingBytes < MMWDEMO_OUTPUT_MSG_SEGMENT_LEN)
                {
                    mmw_UartWrite (uartHandle, (uint8_t*)padding, numPaddingBytes);
                }
            }

        }
        /* Flush UART buffer here for each frame. */
        UART_flushTxFifo(uartHandle);

        /* End of UART data transmission */
        gMmwMssMCB.stats.uartTransferEndTimeStamp = Cycleprofiler_getTimeStamp();
        gMmwMssMCB.outStats.transmitOutputTime = (gMmwMssMCB.stats.uartTransferEndTimeStamp - gMmwMssMCB.stats.interFrameEndTimeStamp)/FRAME_REF_TIMER_CLOCK_MHZ;
        gMmwMssMCB.stats.totalActiveTime_us = (gMmwMssMCB.stats.uartTransferEndTimeStamp - gMmwMssMCB.stats.frameStartTimeStamp)/FRAME_REF_TIMER_CLOCK_MHZ;
        
        //Interframe processing and UART data transmission completed 
        gMmwMssMCB.interSubFrameProcToken--;

        // Capture the time elaspsed till here
        demoEndTime = PRCMSlowClkCtrGet();
        // Demo Run time for one frame (From Sensor Start till Completion of UART transmit)
        demoTimeus = (demoEndTime - demoStartTime)*(30.5);

        #if (CLI_REMOVAL == 0)
        if (gMmwMssMCB.adcDataSourceCfg.source == 1 || gMmwMssMCB.adcDataSourceCfg.source == 2)
        {
            demoTimeus = 0;
        }
        #endif
        
        if((gMmwMssMCB.lowPowerMode == LOW_PWR_MODE_ENABLE) || (gMmwMssMCB.lowPowerMode == LOW_PWR_TEST_MODE))
        {
            xSemaphoreGive(gPowerSem);
            if(gMmwMssMCB.lowPowerMode == LOW_PWR_MODE_ENABLE)
            {
                Power_enablePolicy();
            }
        }

        if (gMmwMssMCB.lowPowerMode == LOW_PWR_MODE_DISABLE)
        {
            #if (CLI_REMOVAL == 0)
            if(gMmwMssMCB.adcDataSourceCfg.source == 1 || gMmwMssMCB.adcDataSourceCfg.source == 2)
            {
                /* In test mode trigger next frame processing */
                SemaphoreP_post(&gMmwMssMCB.adcFileTaskSemHandle);
            }
            #endif
            // Important Note: Sensor Stop command is honoured only when Low Power Cfg is disabled
            if(sensorStop == 1)
            {
                MmwDemo_stopSensor();
            }
        }
        /* Trigger DPC task to send chirps and treat data */
        SemaphoreP_post(&gMmwMssMCB.tlvTaskDoneSemHandle);
        uint32_t cycleCount = CycleCounterP_getCount32()-startCycle;
        DebugP_log("TLV loop task time = CPU cycles = %d !!!\r\n", cycleCount);

    }
}

void MMWave_findRangeGates(DPIF_CFARRngDopDetListElement * detRngDopList, uint32_t numDetectedPoints, DPIF_DetectedRangeGates *rangeGates)
{
    uint32_t rangeGateIdx = 0;
    uint32_t pointIdx = 0;
    uint32_t maxNumRangeGates = rangeGates->maxNumRangeGates;
    DPIF_DetectedRangeGate *rngGateArray = rangeGates->array;

    if (numDetectedPoints == 0)
    {
       goto exit;
    }

    /*Set the first range gate */
    rngGateArray[rangeGateIdx].rangeIdx = detRngDopList[pointIdx].rangeIdx;
    rngGateArray[rangeGateIdx].numDopplerBins = 1;
    rangeGateIdx++;

    for (int pointIdx = 1; pointIdx < numDetectedPoints; pointIdx++)
    {
       if (detRngDopList[pointIdx].rangeIdx == detRngDopList[pointIdx-1].rangeIdx)
       {
           rngGateArray[rangeGateIdx-1].numDopplerBins++;
       }
       else
       {
           rngGateArray[rangeGateIdx].rangeIdx = detRngDopList[pointIdx].rangeIdx;
           rngGateArray[rangeGateIdx].numDopplerBins = 1;
           rangeGateIdx++;
           if (rangeGateIdx == maxNumRangeGates)
           {
               break;
           }
       }
    }

exit:
    rangeGates->numRangeGates = rangeGateIdx;
}

int32_t mmwDemo_mmWaveInit(bool iswarmstrt)
{
    int32_t             errCode;
    int32_t             retVal = SystemP_SUCCESS;
    MMWave_InitCfg      initCfg;
    MMWave_ErrorLevel   errorLevel;
    int16_t             mmWaveErrorCode;
    int16_t             subsysErrorCode;

    /* Initialize the mmWave control init configuration */
    memset ((void*)&initCfg, 0, sizeof(MMWave_InitCfg));

    /* Is Warm Start? */
    initCfg.iswarmstart = iswarmstrt;

    /* Initialize and setup the mmWave Control module */
    gMmwMssMCB.ctrlHandle = MMWave_init (&initCfg, &errCode);
    if (gMmwMssMCB.ctrlHandle == NULL)
    {
        /* Error: Unable to initialize the mmWave control module */
        MMWave_decodeError (errCode, &errorLevel, &mmWaveErrorCode, &subsysErrorCode);

        /* Error: Unable to initialize the mmWave control module */
        CLI_write ("Error: mmWave Control Initialization failed [Error code %d] [errorLevel %d] [mmWaveErrorCode %d] [subsysErrorCode %d]\n", errCode, errorLevel, mmWaveErrorCode, subsysErrorCode);
        retVal = SystemP_FAILURE;
    }
    /* FECSS RF Power ON*/
    if(initCfg.iswarmstart)
    {
        errCode = rl_fecssRfPwrOnOff(M_DFP_DEVICE_INDEX_0, &gMmwMssMCB.channelCfg);
        if(errCode != M_DFP_RET_CODE_OK)
        {
            CLI_write ("Error: FECSS RF PowerON failed [Error code %d] \r\n", errCode);
            retVal = SystemP_FAILURE;
        }   
    }

    return retVal;
}

/**
 *  @b Description
 *  @n
 *      mmw demo helper Function to start sensor.
 *
 *  @retval
 *      Success     - 0
 *  @retval
 *      Error       - <0
 */
int32_t MmwDemo_startSensor(void)
{
#if !(CONTINUOUS_WAVE_MODE_ENABLE) /* suppress warning */
    int32_t     errCode;
#endif
    MMWave_CalibrationCfg   calibrationCfg;


    /*****************************************************************************
     * RF :: now start the RF and the real time ticking
     *****************************************************************************/
    /* Initialize the calibration configuration: */
    memset ((void *)&calibrationCfg, 0, sizeof(MMWave_CalibrationCfg));
    /* Populate the calibration configuration: */
    Mmwave_populateDefaultCalibrationCfg (&calibrationCfg);

    DebugP_logInfo("App: MMWave_start Issued\n");

#if !(CONTINUOUS_WAVE_MODE_ENABLE) /* disable mmWave_start for continousMode CW */
    /* Start the mmWave module: The configuration has been applied successfully. */
    if (MMWave_start(gMmwMssMCB.ctrlHandle, &calibrationCfg, &gMmwMssMCB.sensorStart, &errCode) < 0)
    {
        MMWave_ErrorLevel   errorLevel;
        int16_t             mmWaveErrorCode;
        int16_t             subsysErrorCode;

        /* Error/Warning: Unable to start the mmWave module */
        MMWave_decodeError (errCode, &errorLevel, &mmWaveErrorCode, &subsysErrorCode);
        CLI_write ("Error: mmWave Start failed [mmWave Error: %d Subsys: %d]\n", mmWaveErrorCode, subsysErrorCode);
        /* datapath has already been moved to start state; so either we initiate a cleanup of start sequence or
           assert here and re-start from the beginning. For now, choosing the latter path */
        MmwDemo_debugAssert(0);
        return -1;
    }
#endif
    return 0;
}

/**
 *  @b Description
 *  @n
 *      MMW Demo helper Function to Stop the Sensor. Sensor Stop in honoured only when Low Power Mode is disabled.
 *
 *  @retval
 *      None
 */
void MmwDemo_stopSensor(void)
{
    int32_t err;
    // Stop and Close the front end
    MMWave_stop(gMmwMssMCB.ctrlHandle,&err);
    MMWave_close(gMmwMssMCB.ctrlHandle,&err);
    // Delete the exisitng profile as we receive a new configuration
    MMWave_delProfile(gMmwMssMCB.ctrlHandle,gMmwMssMCB.mmwCtrlCfg.frameCfg[0].profileHandle[0],&err);
    // Free up all the edma channels and close the EDMA interface 
    mmwDemo_freeDmaChannels(gEdmaHandle[0]);
    Drivers_edmaClose();
    EDMA_deinit();
    // Demo Stopped
    rangeProcHWAObj* temp = gMmwMssMCB.rangeProcDpuHandle;
    temp->inProgress = false;
    gMmwMssMCB.oneTimeConfigDone = 0;
    // Re-init the EDMA interface for next configuration
    EDMA_init();
    Drivers_edmaOpen();
    gMmwMssMCB.stats.frameStartIntCounter = 0;
    sensorStop = 0;
    isSensorStarted = 0;

    // Delete the DPC, TLV as we will create them again in next configuration when we start
    vTaskDelete(gDpcTask);
    vTaskDelete(NULL);
}

/**
 *  @b Description
 *  @n
 *      mmw demo helper Function to do one time sensor initialization.
 *      User need to fill gMmwMssMCB.mmwOpenCfg before calling this function
 *
 *  @retval
 *      Success     - 0
 *  @retval
 *      Error       - <0
 */
int32_t MmwDemo_openSensor(void)
{
    int32_t             errCode;
    MMWave_ErrorLevel   errorLevel;
    int16_t             mmWaveErrorCode;
    int16_t             subsysErrorCode;

    /**********************************************************
     **********************************************************/

    /* Open mmWave module, this is only done once */

    /* Open the mmWave module: */
    if (MMWave_open (gMmwMssMCB.ctrlHandle, &gMmwMssMCB.mmwOpenCfg, &errCode) < 0)
    {
        /* Error: decode and Report the error */
        MMWave_decodeError (errCode, &errorLevel, &mmWaveErrorCode, &subsysErrorCode);
        CLI_write ("Error: mmWave Open failed [Error code: %d Subsystem: %d]\n",
                        mmWaveErrorCode, subsysErrorCode);
        return -1;
    }

    return 0;
}

/**
 *  @b Description
 *  @n
 *      MMW demo helper Function to configure sensor. User need to fill gMmwMssMCB.mmwCtrlCfg and
 *      add profiles/chirp to mmWave before calling this function
 *
 *  @retval
 *      Success     - 0
 *  @retval
 *      Error       - <0
 */
int32_t MmwDemo_configSensor(void)
{
    int32_t     errCode = 0;

    /* Configure the mmWave module: */
    if (MMWave_config (gMmwMssMCB.ctrlHandle, &gMmwMssMCB.mmwCtrlCfg, &errCode) < 0)
    {
        MMWave_ErrorLevel   errorLevel;
        int16_t             mmWaveErrorCode;
        int16_t             subsysErrorCode;

        /* Error: Report the error */
        MMWave_decodeError (errCode, &errorLevel, &mmWaveErrorCode, &subsysErrorCode);
        CLI_write ("Error: mmWave Config failed [Error code: %d Subsystem: %d]\n",
                        mmWaveErrorCode, subsysErrorCode);
        goto exit;
    }

exit:
    return errCode;
}

void mmwave_demo(void* args)
{
    int32_t errorCode = SystemP_SUCCESS;
    int32_t retVal = -1;

    /* Peripheral Driver Initialization */
    Drivers_open();
    Board_driversOpen();
    
    // Get the version of Device.
    pgVersion = SOC_getEfusePgVersion();

    // Configure the LED GPIO
    gpioBaseAddrLed = (uint32_t) AddrTranslateP_getLocalAddr(GPIO_LED_BASE_ADDR);
    pinNumLed       = GPIO_LED_PIN;
    GPIO_setDirMode(gpioBaseAddrLed, pinNumLed, GPIO_LED_DIR);

    /*HWASS_SHRD_RAM, TPCCA and TPCCB memory have to be init before use. */
    /*APPSS SHRAM0 and APPSS SHRAM1 memory have to be init before use. However, for awrL varients these are initialized by RBL */
    /*FECSS SHRAM (96KB) has to be initialized before use as RBL does not perform initialization.*/
    SOC_memoryInit(SOC_RCM_MEMINIT_HWA_SHRAM_INIT|SOC_RCM_MEMINIT_TPCCA_INIT|SOC_RCM_MEMINIT_TPCCB_INIT|SOC_RCM_MEMINIT_FECSS_SHRAM_INIT|SOC_RCM_MEMINIT_APPSS_SHRAM0_INIT|SOC_RCM_MEMINIT_APPSS_SHRAM1_INIT);

    /* Is the device 6432 AOP */
    #ifdef SOC_XWRL64XX
    gMmwMssMCB.isDevAOP = SOC_isDeviceAOP();
    #endif

    gMmwMssMCB.commandUartHandle = gUartHandle[0];

    /* mmWave initialization*/
    mmwDemo_mmWaveInit(0);

    /* Initialize default antenna geometry */
    memcpy((void *) &gMmwMssMCB.antennaGeometryCfg, (void *) &gDefaultAntGeometry, sizeof(MmwDemo_antennaGeometryCfg));

    gmmwinitTask = xTaskCreateStatic( mmwreinitTask,      /* Pointer to the function that implements the task. */
                                  "mmwinit",          /* Text name for the task.  This is to facilitate debugging only. */
                                  MMWINIT_TASK_SIZE,  /* Stack depth in units of StackType_t typically uint32_t on 32b CPUs */
                                  NULL,            /* We are not using the task parameter. */
                                  MMWINITTASK_PRI,   /* task priority, 0 is lowest priority, configMAX_PRIORITIES-1 is highest */
                                  gmmwinitTaskStack,  /* pointer to stack base */
                                  &gmmwinitTaskObj ); /* pointer to statically allocated task object memory */
    gmmwinit = xSemaphoreCreateBinaryStatic(&gmmwinitObj);

    // Radar Power Management Framework: Create a Task for Power Management Framework
    gPowerTask = xTaskCreateStatic( powerManagementTask,      /* Pointer to the function that implements the task. */
                                  "power",          /* Text name for the task.  This is to facilitate debugging only. */
                                  POWER_TASK_SIZE,  /* Stack depth in units of StackType_t typically uint32_t on 32b CPUs */
                                  NULL,            /* We are not using the task parameter. */
                                  POWER_TASK_PRI,   /* task priority, 0 is lowest priority, configMAX_PRIORITIES-1 is highest */
                                  gPowerTaskStack,  /* pointer to stack base */
                                  &gPowerTaskObj ); /* pointer to statically allocated task object memory */
                                  
    //Radar Power Management Framework: Create Semaphore for to pend Power Task
    gPowerSem = xSemaphoreCreateBinaryStatic(&gPowerSemObj);

    /* Create binary semaphore to pend Main task, */
    SemaphoreP_constructBinary(&gMmwMssMCB.demoInitTaskCompleteSemHandle, 0);

    errorCode = SemaphoreP_constructBinary(&gMmwMssMCB.cliInitTaskCompleteSemHandle, 0);
    DebugP_assert(SystemP_SUCCESS == errorCode);

    errorCode = SemaphoreP_constructBinary(&gMmwMssMCB.TestSemHandle, 0);
    DebugP_assert(SystemP_SUCCESS == errorCode);

    errorCode = SemaphoreP_constructBinary(&gMmwMssMCB.tlvSemHandle, 0);
    DebugP_assert(SystemP_SUCCESS == errorCode);

    errorCode = SemaphoreP_constructBinary(&gMmwMssMCB.adcFileTaskSemHandle, 0);
    DebugP_assert(SystemP_SUCCESS == errorCode);

    errorCode = SemaphoreP_constructBinary(&gMmwMssMCB.tlvTaskDoneSemHandle, 0);
    DebugP_assert(SystemP_SUCCESS == errorCode);

    errorCode = SemaphoreP_constructBinary(&gMmwMssMCB.dpcTaskConfigDoneSemHandle, 0);
    DebugP_assert(SystemP_SUCCESS == errorCode);
    errorCode = SemaphoreP_constructBinary(&gMmwMssMCB.uartTaskConfigDoneSemHandle, 0);
    DebugP_assert(SystemP_SUCCESS == errorCode);
#if (ENABLE_MONITORS==1)
    /*Creating Semaphore for Monitors*/
    errorCode = SemaphoreP_constructBinary(&gMmwMssMCB.rfmonSemHandle, 0);
    DebugP_assert(SystemP_SUCCESS == errorCode);
#endif

    /* Initialize Flash interface. */
    retVal = mmwDemo_flashInit();
    if (retVal < 0)
    {
        CLI_write("Error: Flash Initialization Failed!\r\n");
        MmwDemo_debugAssert (0);
    }

    /* Check if the device is RF-Trimmed */
    /* Checking one Trim is enough */
    if(SOC_rcmReadSynthTrimValid() == RF_SYNTH_TRIM_VALID)
    {
        gMmwMssMCB.factoryCalCfg.atecalibinEfuse = true;
    }
    else
    {
        gMmwMssMCB.factoryCalCfg.atecalibinEfuse = false;
        CLI_write("Error: Device is not RF-Trimmed!\r\n");
        MmwDemo_debugAssert (0);
    }

    /* DPC initialization*/
    DPC_Init();

    // Make the LED HIGH
    GPIO_pinWriteHigh(gpioBaseAddrLed, pinNumLed);

    CLI_init(CLI_TASK_PRIORITY);

    /* Never return for this task. */
    SemaphoreP_pend(&gMmwMssMCB.demoInitTaskCompleteSemHandle, SystemP_WAIT_FOREVER);

    Board_driversClose();
    Drivers_close();
}

// Free all the allocated EDMA channels
void mmwDemo_freeDmaChannels(EDMA_Handle edmaHandle)
{
    uint32_t   index;
    uint32_t  dmaCh, tcc, pram, shadow;
    for(index = 0; index < 64; index++)
    {
        dmaCh = index;
        tcc = index;
        pram = index;
        shadow = index;
        DPEDMA_freeEDMAChannel(edmaHandle, &dmaCh, &tcc, &pram, &shadow);
    }
    for(index = 0; index < 128; index++)
    {
        shadow = index;
        DebugP_assert(EDMA_freeParam(edmaHandle, &shadow) == SystemP_SUCCESS);
    }
    return;
}
