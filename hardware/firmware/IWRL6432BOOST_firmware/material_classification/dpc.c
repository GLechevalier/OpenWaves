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
#include <kernel/dpl/CycleCounterP.h>
#include "FreeRTOS.h"
#include "task.h"
/* mmwave SDK files */
#include <control/mmwave/mmwave.h>
#include "source/mmw_cli.h"
#include "ti_drivers_config.h"
#include "ti_drivers_open_close.h"
#include "ti_board_open_close.h"
#include "ti_board_config.h"
#include <FreeRTOS.h>
#include <task.h>
#include <semphr.h>
#include "drivers/power.h"
#include <drivers/prcm.h>
#include <drivers/hwa.h>

#include <alg/caponBeamforming2D_remake/caponBeamforming2D.h>

#include <utils/mathutils/mathutils.h>

#include "source/mmwave_demo.h"
#include "source/mmw_res.h"
#include "source/dpc/dpc.h"
#include "source/mmwave_control/interrupts.h"
#include "source/calibrations/range_phase_bias_measurement.h"
#include "source/utils/mmw_demo_utils.h"

#define HWA_MAX_NUM_DMA_TRIG_CHANNELS 16
#define MAX_NUM_DETECTIONS          (MMWDEMO_OUTPUT_POINT_CLOUD_LIST_MAX_SIZE)

#define LOW_PWR_MODE_DISABLE (0)
#define LOW_PWR_MODE_ENABLE (1)
#define LOW_PWR_TEST_MODE (2)

#define MMW_DEMO_MAJOR_MODE 0
#define MMW_DEMO_MINOR_MODE 1

#define FRAME_REF_TIMER_CLOCK_MHZ  40

/* Max Frame Size for FTDI chip is 64KB */
#define MAXSPISIZEFTDI               (65536U)

#define DPC_DPU_DOPPLERPROC_FFT_WINDOW_TYPE MATHUTILS_WIN_HANNING
#define DOPPLER_OUTPUT_MAPPING_DOP_ROW_COL   0
#define DOPPLER_OUTPUT_MAPPING_ROW_DOP_COL   1
#define DPC_OBJDET_QFORMAT_DOPPLER_FFT 17

#define MMWDEMO_RFPARSER_SPEED_OF_LIGHT_IN_METERS_PER_SEC (3e8)

#define DPC_DPU_DOPPLERPROC_FFT_WINDOW_TYPE MATHUTILS_WIN_HANNING

#define DPC_OBJDET_QFORMAT_DOPPLER_FFT 17

#define DPC_OBJDET_HWA_WINDOW_RAM_OFFSET 0
#define DPC_DPU_RANGEPROC_FFT_WINDOW_TYPE MATHUTILS_WIN_BLACKMAN
#define DPC_OBJDET_QFORMAT_RANGE_FFT 17
#define MMW_DEMO_TEST_ADC_BUFF_SIZE 1024  //maximum 128 real samples (int16_t), 3 Rx channels

#define DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_CH_CAPONSPECTRUM                 EDMA_APPSS_TPCC_B_EVT_HWA_DMA_REQ11
#define DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_SHADOW_CAPONSPECTRUM             (DPC_OBJDET_EDMA_SHADOW_BASE + 11)
#define DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_EVENT_QUE_CAPONSPECTRUM          1

#define DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_SIG_CH_CAPONSPECTRUM             EDMA_APPSS_TPCC_B_EVT_FREE_5
#define DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_SIG_SHADOW_CAPONSPECTRUM         (DPC_OBJDET_EDMA_SHADOW_BASE + 13)
#define DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_SIG_EVENT_QUE_CAPONSPECTRUM      1

#define DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAOUT_CAPONSPECTRUM_CH                EDMA_APPSS_TPCC_B_EVT_HWA_DMA_REQ2
#define DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAOUT_CAPONSPECTRUM_SHADOW            (DPC_OBJDET_EDMA_SHADOW_BASE + 15)
#define DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAOUT_CAPONSPECTRUM_EVENT_QUE         1

#define MAX_RANGE_BINS_SKIP         (2U)
#define MMW_DEMO_TEST_CAPON_INPUT_SIZE                                          MAX_NUM_SNAPSHOTS * MAX_NUM_TX_ANTENNA * MAX_NUM_RX_ANTENNA


int32_t caponInputData[2*MMW_DEMO_TEST_CAPON_INPUT_SIZE] __attribute__((section(".data"), aligned(32)));
float   caponSpectrum[MAX_ANGLES_AZIMUTH*MAX_ANGLES_ELEVATION*MAX_RANGE_BINS_SKIP] __attribute__((section(".data"), aligned(32)));



extern MmwDemo_MSS_MCB gMmwMssMCB;
extern HWA_Handle hwaHandle;

#define L3_MEM_SIZE (0x40000 + 160*1024)
extern uint8_t gMmwL3[L3_MEM_SIZE]  __attribute((section(".l3")));
/*! Local RAM buffer for object detection DPC */
#define MMWDEMO_OBJDET_CORE_LOCAL_MEM_SIZE ((8U+6U+4U+2U+8U) * 1024U)
extern uint8_t gMmwCoreLocMem[MMWDEMO_OBJDET_CORE_LOCAL_MEM_SIZE];
/*! Local RAM buffer for tracker */
#define MMWDEMO_OBJDET_CORE_LOCAL_MEM2_SIZE (25U * 1024U)
uint8_t gMmwCoreLocMem2[MMWDEMO_OBJDET_CORE_LOCAL_MEM2_SIZE];
/* User defined heap memory and handle */
#define MMWDEMO_OBJDET_CORE_LOCAL_MEM3_SIZE  (2*1024u)
extern uint8_t gMmwCoreLocMem3[MMWDEMO_OBJDET_CORE_LOCAL_MEM3_SIZE] __attribute__((aligned(HeapP_BYTE_ALIGNMENT)));

extern uint8_t pgVersion;

// LED config
extern uint32_t gpioBaseAddrLed, pinNumLed;
extern MMWave_temperatureStats  tempStats;

extern DPU_DoaProc_HW_Resources  *hwRes;

volatile unsigned long long test;
void mmwDemo_dpcTask();

CaponBeamforming2DHWA_Config      caponBeamformingCfg;
DPU_RangeProcHWA_Config rangeProcDpuCfg;

/*! @brief     EDMA interrupt objects for DPUs */

Edma_IntrObject     intrObj_CaponBeamforming;
Edma_IntrObject     intrObj_rangeProc[2];

/**
 *  @b Description
 *  @n
 *      The function allocates HWA DMA source channel from the pool
 *
 *  @param[in]  pool Handle to pool object.
 *
 *  @retval
 *      channel Allocated HWA trigger source channel
 */
uint8_t DPC_ObjDet_HwaDmaTrigSrcChanPoolAlloc(HwaDmaTrigChanPoolObj *pool)
{
    uint8_t channel = 0xFF;
    if(pool->dmaTrigSrcNextChan < HWA_MAX_NUM_DMA_TRIG_CHANNELS)
    {
        channel = pool->dmaTrigSrcNextChan;
        pool->dmaTrigSrcNextChan++;
    }
    return channel;
}

/**
 *  @b Description
 *  @n
 *      The function resets HWA DMA source channel pool
 *
 *  @param[in]  pool Handle to pool object.
 *
 *  @retval
 *      none
 */
void DPC_ObjDet_HwaDmaTrigSrcChanPoolReset(HwaDmaTrigChanPoolObj *pool)
{
    pool->dmaTrigSrcNextChan = 0;
}

/**
 *  @b Description
 *  @n
 *      The function allocates memory in HWA RAM memory pool
 *
 *  @param[in]  pool Handle to pool object.
 *
 *  @retval
 *      startSampleIndex sample index in the HWA RAM memory
 */
int16_t DPC_ObjDet_HwaWinRamMemoryPoolAlloc(HwaWinRamMemoryPoolObj *pool, uint16_t numSamples)
{
    int16_t startSampleIndex = -1;
    if((pool->memStartSampleIndex + numSamples) < (CSL_APP_HWA_WINDOW_RAM_U_SIZE/sizeof(uint32_t)))
    {
        startSampleIndex = pool->memStartSampleIndex;
        pool->memStartSampleIndex += numSamples;
    }
    return startSampleIndex;
}

/**
 *  @b Description
 *  @n
 *      The function resets HWA DMA source channel pool
 *
 *  @param[in]  pool Handle to pool object.
 *
 *  @retval
 *      none
 */
void DPC_ObjDet_HwaWinRamMemoryPoolReset(HwaWinRamMemoryPoolObj *pool)
{
    pool->memStartSampleIndex = 0;
}

/**
 *  @b Description
 *  @n
 *      Utility function for reseting memory pool.
 *
 *  @param[in]  pool Handle to pool object.
 *
 *  \ingroup DPC_OBJDET__INTERNAL_FUNCTION
 *
 *  @retval
 *      none.
 */
void DPC_ObjDet_MemPoolReset(MemPoolObj *pool)
{
    pool->currAddr = (uintptr_t)pool->cfg.addr;
    pool->maxCurrAddr = pool->currAddr;
}


/**
 *  @b Description
 *  @n
 *      Utility function for setting memory pool to desired address in the pool.
 *      Helps to rewind for example.
 *
 *  @param[in]  pool Handle to pool object.
 *  @param[in]  addr Address to assign to the pool's current address.
 *
 *  \ingroup DPC_OBJDET__INTERNAL_FUNCTION
 *
 *  @retval
 *      None
 */
void DPC_ObjDet_MemPoolSet(MemPoolObj *pool, void *addr)
{
    pool->currAddr = (uintptr_t)addr;
    pool->maxCurrAddr = MAX(pool->currAddr, pool->maxCurrAddr);
}

/**
 *  @b Description
 *  @n
 *      Utility function for getting memory pool current address.
 *
 *  @param[in]  pool Handle to pool object.
 *
 *  \ingroup DPC_OBJDET__INTERNAL_FUNCTION
 *
 *  @retval
 *      pointer to current address of the pool (from which next allocation will
 *      allocate to the desired alignment).
 */
void *DPC_ObjDet_MemPoolGet(MemPoolObj *pool)
{
    return((void *)pool->currAddr);
}

/**
 *  @b Description
 *  @n
 *      Utility function for getting maximum memory pool usage.
 *
 *  @param[in]  pool Handle to pool object.
 *
 *  \ingroup DPC_OBJDET__INTERNAL_FUNCTION
 *
 *  @retval
 *      Amount of pool used in bytes.
 */
uint32_t DPC_ObjDet_MemPoolGetMaxUsage(MemPoolObj *pool)
{
    return((uint32_t)(pool->maxCurrAddr - (uintptr_t)pool->cfg.addr));
}

/**
 *  @b Description
 *  @n
 *      Utility function for allocating from a static memory pool.
 *
 *  @param[in]  pool Handle to pool object.
 *  @param[in]  size Size in bytes to be allocated.
 *  @param[in]  align Alignment in bytes
 *
 *  \ingroup DPC_OBJDET__INTERNAL_FUNCTION
 *
 *  @retval
 *      pointer to beginning of allocated block. NULL indicates could not
 *      allocate.
 */
void *DPC_ObjDet_MemPoolAlloc(MemPoolObj *pool,
                              uint32_t size,
                              uint8_t align)
{
    void *retAddr = NULL;
    uintptr_t addr;

    addr = MEM_ALIGN(pool->currAddr, align);
    if ((addr + size) <= ((uintptr_t)pool->cfg.addr + pool->cfg.size))
    {
        retAddr = (void *)addr;
        pool->currAddr = addr + size;
        pool->maxCurrAddr = MAX(pool->currAddr, pool->maxCurrAddr);
    }

    return(retAddr);
}

/**
 *  @b Description
 *  @n
 *      Utility function to do a parabolic/quadratic fit on 3 input points
 *      and return the coordinates of the peak. This is used to accurately estimate
 *      range bias.
 *
 *  @param[in]  x Pointer to array of 3 elements representing the x-coordinate
 *              of the points to fit
 *  @param[in]  y Pointer to array of 3 elements representing the y-coordinate
 *              of the points to fit
 *  @param[out] xv Pointer to output x-coordinate of the peak value
 *  @param[out] yv Pointer to output y-coordinate of the peak value
 *
 *  @retval   None
 *
 */
void rangeBiasRxChPhaseMeasure_quadfit(float *x, float*y, float *xv, float *yv)
{
    float a, b, c, denom;
    float x0 = x[0];
    float x1 = x[1];
    float x2 = x[2];
    float y0 = y[0];
    float y1 = y[1];
    float y2 = y[2];

    denom = (x0 - x1)*(x0 - x2)*(x1 - x2);
    if (denom != 0.)
    {
        a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom;
        b = (x2*x2 * (y0 - y1) + x1*x1 * (y2 - y0) + x0*x0 * (y1 - y2)) / denom;
        c = (x1 * x2 * (x1 - x2) * y0 + x2 * x0 * (x2 - x0) * y1 + x0 * x1 * (x0 - x1) * y2) / denom;
    }
    else
    {
        *xv = x[1];
        *yv = y[1];
        return;
    }
    if (a != 0.)
    {
        *xv = -b/(2*a);
        *yv = c - b*b/(4*a);
    }
    else
    {
        *xv = x[1];
        *yv = y[1];
    }
}

/**
*  @b Description
*  @n
*    Function to construct feature extract heap
*/
void featExtract_heapConstruct()
{
    HeapP_construct(&gMmwMssMCB.CoreLocalFeatExtractHeapObj, (void *) gMmwCoreLocMem3, MMWDEMO_OBJDET_CORE_LOCAL_MEM3_SIZE);
}

/**
*  @b Description
*  @n
*    Function to allocate memory for feature extract heap
*/
void *featExtract_malloc(uint32_t sizeInBytes)
{
    return HeapP_alloc(&gMmwMssMCB.CoreLocalFeatExtractHeapObj, sizeInBytes);
}

/**
*  @b Description
*  @n
*    Function to free memory from feature extract heap
*/
void featExtract_free(void *pFree, uint32_t sizeInBytes)
{
    HeapP_free(&gMmwMssMCB.CoreLocalFeatExtractHeapObj, pFree);
}

/**
*  @b Description
*  @n
*    Function to get memory usage stats of feature extract heap object
*/
uint32_t featExtract_memUsage()
{
    uint32_t usedMemSizeInBytes;
    HeapP_MemStats heapStats;

    HeapP_getHeapStats(&gMmwMssMCB.CoreLocalFeatExtractHeapObj, &heapStats);
    usedMemSizeInBytes = sizeof(gMmwCoreLocMem3) - heapStats.availableHeapSpaceInBytes;

    return usedMemSizeInBytes;
}

/**
*  @b Description
*  @n
*    Select coordinates of active virtual antennas and calculate the size of the 2D virtual antenna pattern,
*    i.e. number of antenna rows and number of antenna columns.
*/
void MmwDemo_calcActiveAntennaGeometry()
{
    int32_t txInd, rxInd, ind;
    int32_t rowMax, colMax;
    int32_t rowMin, colMin;
    /* Select only active antennas */
    ind = 0;
    for (txInd = 0; txInd < gMmwMssMCB.numTxAntennas; txInd++)
    {
        for (rxInd = 0; rxInd < gMmwMssMCB.numRxAntennas; rxInd++)
        {
            gMmwMssMCB.activeAntennaGeometryCfg.ant[ind] = gMmwMssMCB.antennaGeometryCfg.ant[gMmwMssMCB.rxAntOrder[rxInd] + (txInd * SYS_COMMON_NUM_RX_CHANNEL)];
            ind++;
        }
    }

    /* Calculate virtual antenna 2D array size */
    ind = 0;
    rowMax = 0;
    colMax = 0;
    rowMin = 127;
    colMin = 127;
    for (txInd = 0; txInd < gMmwMssMCB.numTxAntennas; txInd++)
    {
        for (rxInd = 0; rxInd < gMmwMssMCB.numRxAntennas; rxInd++)
        {
            if (gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].row > rowMax)
            {
                rowMax = gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].row;
            }
            if (gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].col > colMax)
            {
                colMax = gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].col;
            }
            if (gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].row < rowMin)
            {
                rowMin = gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].row;
            }
            if (gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].col < colMin)
            {
                colMin = gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].col;
            }
            ind++;
        }
    }
    ind = 0;
    for (txInd = 0; txInd < gMmwMssMCB.numTxAntennas; txInd++)
    {
        for (rxInd = 0; rxInd < gMmwMssMCB.numRxAntennas; rxInd++)
        {
            gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].row -= rowMin;
            gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].col -= colMin;
            ind++;
        }
    }
    gMmwMssMCB.numAntRow = rowMax - rowMin + 1;
    gMmwMssMCB.numAntCol = colMax - colMin + 1;
}

/**
*  @b Description
*  @n
*    Based on the activeAntennaGeometryCfg configures the table which used to configure
*    Doppler FFT HWA param sets in DoA DPU. THese param sets perform Doppler FFT and
*    at the same time mapping of input antennas into 2D row-column antenna array where columns
*    are in  azimuth dimension, and rows in elevation dimension.
*    It also calculates the size of 2D antenna array, ie. number of rows and number of columns.
*/
int32_t MmwDemo_cfgDopplerParamMapping(DPU_Aoa2dProc_HWA_Option_Cfg *dopplerParamCfg, uint32_t mappingOption)
{
    int32_t ind, indNext, indNextPrev;
    int32_t row, col;
    int32_t dopParamInd;
    int32_t state;
    int16_t BT[DPU_DOA_PROC_MAX_2D_ANT_ARRAY_ELEMENTS];
    int16_t DT[DPU_DOA_PROC_MAX_2D_ANT_ARRAY_ELEMENTS];
    int16_t SCAL[DPU_DOA_PROC_MAX_2D_ANT_ARRAY_ELEMENTS];
    int8_t  DONE[DPU_DOA_PROC_MAX_2D_ANT_ARRAY_ELEMENTS];
    int32_t retVal = 0;
    int32_t rowOffset;

    if (gMmwMssMCB.numAntRow * gMmwMssMCB.numAntCol > DPU_DOA_PROC_MAX_2D_ANT_ARRAY_ELEMENTS)
    {
        retVal = DPC_OBJECTDETECTION_EANTENNA_GEOMETRY_CFG_FAILED;
        goto exit;
    }

    if (mappingOption == DOPPLER_OUTPUT_MAPPING_DOP_ROW_COL)
    {
        /*For AOA DPU, Output is */
        rowOffset =  gMmwMssMCB.numAntCol;
    }
    else if (mappingOption == DOPPLER_OUTPUT_MAPPING_ROW_DOP_COL)
    {
        rowOffset =  gMmwMssMCB.numDopplerBins * gMmwMssMCB.numAntCol;
    }
    else
    {
        retVal = DPC_OBJECTDETECTION_EANTENNA_GEOMETRY_CFG_FAILED;
        goto exit;
    }

    /* Initialize tables */
    for (ind = 0; ind < (gMmwMssMCB.numAntRow * gMmwMssMCB.numAntCol); ind++)
    {
        BT[ind] = 0;
        SCAL[ind] = 0;
        DONE[ind] = 0;
    }

    for (ind = 0; ind < (gMmwMssMCB.numTxAntennas * gMmwMssMCB.numRxAntennas); ind++)
    {
        row = gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].row;
        col = gMmwMssMCB.activeAntennaGeometryCfg.ant[ind].col;
        BT[row * gMmwMssMCB.numAntCol + col] = ind;
        SCAL[row * gMmwMssMCB.numAntCol + col] = 1;
    }
    for (row = 0; row < gMmwMssMCB.numAntRow; row++)
    {
        for (col = 0; col < gMmwMssMCB.numAntCol; col++)
        {
            ind = row * gMmwMssMCB.numAntCol + col;
            DT[ind] = row * rowOffset + col;
        }
    }


    /* Configure Doppler HWA mapping params for antenna mapping */
    dopParamInd = 0;
    dopplerParamCfg->numDopFftParams = 0;
    for (ind = 0; ind < (gMmwMssMCB.numAntRow * gMmwMssMCB.numAntCol); ind++)
    {
        if (!DONE[ind])
        {
            if(dopParamInd < DPU_DOA_PROC_MAX_NUM_DOP_FFFT_PARAMS)
            {
                DONE[ind] = 1;
                dopplerParamCfg->numDopFftParams++;
                dopplerParamCfg->dopFftCfg[dopParamInd].srcBcnt = 1;
                dopplerParamCfg->dopFftCfg[dopParamInd].scale = SCAL[ind];
                if (dopplerParamCfg->dopFftCfg[dopParamInd].scale == 0)
                {
                    dopplerParamCfg->dopFftCfg[dopParamInd].srcAddrOffset = 0;
                }
                else
                {
                    dopplerParamCfg->dopFftCfg[dopParamInd].srcAddrOffset = BT[ind];
                }
                dopplerParamCfg->dopFftCfg[dopParamInd].dstAddrOffset = DT[ind];
                state = 1;//STATE_SECOND:
                for (indNext = ind+1; indNext < (gMmwMssMCB.numAntRow * gMmwMssMCB.numAntCol); indNext++)
                {

                    if (!DONE[indNext] && (dopplerParamCfg->dopFftCfg[dopParamInd].scale == SCAL[indNext]))
                    {
                        switch (state)
                        {
                            case 1://STATE_SECOND:
                                dopplerParamCfg->dopFftCfg[dopParamInd].srcBcnt++;
                                DONE[indNext] = 1;
                                if (SCAL[indNext] == 1)
                                {
                                    dopplerParamCfg->dopFftCfg[dopParamInd].srcBidx = BT[indNext] - dopplerParamCfg->dopFftCfg[dopParamInd].srcAddrOffset;
                                }
                                else
                                {
                                    dopplerParamCfg->dopFftCfg[dopParamInd].srcBidx = 0;
                                }
                                dopplerParamCfg->dopFftCfg[dopParamInd].dstBidx = DT[indNext] - DT[ind];
                                indNextPrev = indNext;
                                state = 2;//STATE_NEXT:
                                break;
                            case 2://STATE_NEXT:
                                if (SCAL[indNext] == 1)
                                {
                                    if ((dopplerParamCfg->dopFftCfg[dopParamInd].srcBidx == (BT[indNext] - BT[indNextPrev])) &&
                                        (dopplerParamCfg->dopFftCfg[dopParamInd].dstBidx == (DT[indNext] - DT[indNextPrev])))
                                    {
                                        DONE[indNext] = 1;
                                        dopplerParamCfg->dopFftCfg[dopParamInd].srcBcnt++;
                                        indNextPrev = indNext;
                                    }
                                }
                                else
                                {
                                    if (dopplerParamCfg->dopFftCfg[dopParamInd].dstBidx == (DT[indNext] - DT[indNextPrev]))
                                    {
                                        DONE[indNext] = 1;
                                        dopplerParamCfg->dopFftCfg[dopParamInd].srcBcnt++;
                                        indNextPrev = indNext;
                                    }
                                }
                                break;
                        }
                    }
                }
                dopParamInd++;
            }
            else
            {
                retVal = DPC_OBJECTDETECTION_EANTENNA_GEOMETRY_CFG_FAILED;
                goto exit;
            }
        }
    }

    dopplerParamCfg->numDopFftParams = dopParamInd;

exit:
    return retVal;
}


/**
 *  @b Description
 *  @n
 *     Compress point cloud list which is transferred to the Host via UART.
 *     Floating point values are converted to int16
 *
 * @param[out] pointCloudOut        Compressed point cloud list
 * @param[in]  pointCloudUintRecip  Scales used for conversion from float values to integer value
 * @param[in]  pointCloudIn         Input point cloud list, generated by CFAR DPU
 * @param[in]  numPoints            Number of points in the point cloud list
 *
 *  @retval
 *      Not Applicable.
 */
void MmwDemo_compressPointCloudList(MmwDemo_output_message_UARTpointCloud *pointCloudOut,
                                    MmwDemo_output_message_point_unit *pointCloudUintRecip,
                                    DPIF_PointCloudCartesianExt *pointCloudIn,
                                    uint32_t numPoints)
{
    uint32_t i;
    float xyzUnitScale = pointCloudUintRecip->xyzUnit;
    float dopplerScale = pointCloudUintRecip->dopplerUnit;
    float snrScale = pointCloudUintRecip->snrUint;
    float noiseScale = pointCloudUintRecip->noiseUint;
    uint32_t tempVal;

    for (i = 0; i < numPoints; i++)
    {
        pointCloudOut->point[i].x = (int16_t) roundf(pointCloudIn[i].x * xyzUnitScale); //saturate the values
        pointCloudOut->point[i].y = (int16_t) roundf(pointCloudIn[i].y * xyzUnitScale);
        pointCloudOut->point[i].z = (int16_t) roundf(pointCloudIn[i].z * xyzUnitScale);
        pointCloudOut->point[i].doppler = (int16_t) roundf(pointCloudIn[i].velocity * dopplerScale);
        tempVal = (uint32_t) roundf(pointCloudIn[i].snr * snrScale);
        if (tempVal > 255)
        {
            tempVal = 255;
        }
        pointCloudOut->point[i].snr = (uint8_t) tempVal;
        tempVal = (uint32_t) roundf(pointCloudIn[i].noise * noiseScale);
        if (tempVal > 255)
        {
            tempVal = 255;
        }
        pointCloudOut->point[i].noise = (uint8_t) tempVal;
    }
}

/*  @b Description
*  @n
*    Range processing DPU Initialization
*/
void rangeProc_dpuInit()
{
    int32_t errorCode = 0;
    DPU_RangeProcHWA_InitParams initParams;
    initParams.hwaHandle = hwaHandle;

    /* generate the dpu handler*/
    gMmwMssMCB.rangeProcDpuHandle = DPU_RangeProcHWA_init(&initParams, &errorCode);
    if (gMmwMssMCB.rangeProcDpuHandle == NULL)
    {
        CLI_write("Error: RangeProc DPU initialization returned error %d\n", errorCode);
        DebugP_assert(0);
        return;
    }
}


/*  @b Description
*  @n
*    Capon Beamforming DPU Initialization
*/
void caponBeamforming_dpuInit()
{
    int32_t errorCode = 0;
    CaponBeamforming2DHWA_InitParams initParams;
    CaponBeamforming2DHWA_Handle  caponBeamformingHandle = NULL;
    initParams.hwaHandle = hwaHandle;

    /* generate the dpu handler*/
    caponBeamformingHandle = CaponBeamforming2DHWA_init(&initParams, &errorCode);
    gMmwMssMCB.caponBeamformingHandle = caponBeamformingHandle;

    if (gMmwMssMCB.caponBeamformingHandle == NULL)
    {
        CLI_write("Error: CaponBeamforming DPU initialization returned error %d\n", errorCode);
        DebugP_assert(0);
        return;
    }
}

/**
*  @b Description
*  @n
*    Based on the configuration, set up the range processing DPU configurations
*/
int32_t RangeProc_configParser()
{

    int32_t retVal = 0;
    DPU_RangeProcHWA_HW_Resources *pHwConfig = &rangeProcDpuCfg.hwRes;
    DPU_RangeProcHWA_StaticConfig  * params;
    uint32_t index;
    uint32_t bytesPerRxChan;

    /* Rangeproc DPU */
    pHwConfig = &rangeProcDpuCfg.hwRes;
    params = &rangeProcDpuCfg.staticCfg;

    memset((void *)&rangeProcDpuCfg, 0, sizeof(DPU_RangeProcHWA_Config));

    params->enableMajorMotion = gMmwMssMCB.enableMajorMotion;
    params->enableMinorMotion = gMmwMssMCB.enableMinorMotion;

    params->numFramesPerMinorMotProc = gMmwMssMCB.sigProcChainCfg.numFrmPerMinorMotProc;
    params->numMinorMotionChirpsPerFrame = gMmwMssMCB.sigProcChainCfg.numMinorMotionChirpsPerFrame;
    params->frmCntrModNumFramesPerMinorMot = gMmwMssMCB.frmCntrModNumFramesPerMinorMot;
    params->lowPowerMode = gMmwMssMCB.lowPowerMode;

    gMmwMssMCB.frmCntrModNumFramesPerMinorMot++;
    if(gMmwMssMCB.frmCntrModNumFramesPerMinorMot == gMmwMssMCB.sigProcChainCfg.numFrmPerMinorMotProc)
    {
        gMmwMssMCB.frmCntrModNumFramesPerMinorMot = 0;
    }

    /* hwi configuration */
    pHwConfig = &rangeProcDpuCfg.hwRes;

    /* HWA configurations, not related to per test, common to all test */
    pHwConfig->hwaCfg.paramSetStartIdx = gMmwMssMCB.numUsedHwaParamSets;

    //pHwConfig->hwaCfg.numParamSet = DPU_RANGEPROCHWA_NUM_HWA_PARAM_SETS; //This is calculated in the configuration API
    pHwConfig->hwaCfg.hwaWinRamOffset  = DPC_ObjDet_HwaWinRamMemoryPoolAlloc(&gMmwMssMCB.HwaWinRamMemoryPoolObj,
                                                                               mathUtils_pow2roundup(gMmwMssMCB.profileComCfg.h_NumOfAdcSamples)/2);//DPC_OBJDET_HWA_RANGE_WINDOW_RAM_OFFSET;
    pHwConfig->hwaCfg.hwaWinSym = HWA_FFT_WINDOW_SYMMETRIC; //we store only lower half
    pHwConfig->hwaCfg.dataInputMode = DPU_RangeProcHWA_InputMode_ISOLATED;
    pHwConfig->hwaCfg.dmaTrigSrcChan[0] = DPC_ObjDet_HwaDmaTrigSrcChanPoolAlloc(&gMmwMssMCB.HwaDmaChanPoolObj); //0
    pHwConfig->hwaCfg.dmaTrigSrcChan[1] = DPC_ObjDet_HwaDmaTrigSrcChanPoolAlloc(&gMmwMssMCB.HwaDmaChanPoolObj); //1

    printf("dmaTrigSrcChan %d,  %d\n", rangeProcDpuCfg.hwRes.hwaCfg.dmaTrigSrcChan[0],rangeProcDpuCfg.hwRes.hwaCfg.dmaTrigSrcChan[1]);

    /* edma configuration */
    pHwConfig->edmaHandle  = gEdmaHandle[0];
    /* edma configuration depends on the interleave or non-interleave */

    /* windowing buffer is fixed, size will change*/
    params->windowSize = sizeof(uint32_t) * ((gMmwMssMCB.profileComCfg.h_NumOfAdcSamples +1 ) / 2); //symmetric window, for real samples
    params->window =  (int32_t *)DPC_ObjDet_MemPoolAlloc(&gMmwMssMCB.CoreLocalRamObj,
                                                         params->windowSize,
                                                         sizeof(uint32_t));
    if (params->window == NULL)
    {
        retVal = DPC_OBJECTDETECTION_ENOMEM__CORE_LOCAL_RAM_RANGE_HWA_WINDOW;
        goto exit;
    }

    /* adc buffer buffer, format fixed, interleave, size will change */
    params->ADCBufData.dataProperty.dataFmt = DPIF_DATAFORMAT_REAL16;
    params->ADCBufData.dataProperty.adcBits = 2U; // 12-bit only
    params->ADCBufData.dataProperty.numChirpsPerChirpEvent = 1U;

    #if (CLI_REMOVAL == 0)
    if(gMmwMssMCB.adcDataSourceCfg.source == 0)
    {
        params->ADCBufData.data = (void *)CSL_APP_HWA_ADCBUF_RD_U_BASE;
    }
    else
    {
        gMmwMssMCB.adcTestBuff  = (uint8_t *) DPC_ObjDet_MemPoolAlloc(&gMmwMssMCB.L3RamObj,
                                                                            MMW_DEMO_TEST_ADC_BUFF_SIZE,
                                                                            sizeof(uint32_t));
        if(gMmwMssMCB.adcTestBuff == NULL)
        {
            retVal = DPC_OBJECTDETECTION_ENOMEM__L3_RAM_ADC_TEST_BUFF;
            goto exit;
        }
        params->ADCBufData.data = (void *)gMmwMssMCB.adcTestBuff;

    }
    #else
    params->ADCBufData.data = (void *)CSL_APP_HWA_ADCBUF_RD_U_BASE;
    #endif

    params->numTxAntennas = (uint8_t) gMmwMssMCB.numTxAntennas;
    params->numVirtualAntennas = (uint8_t) (gMmwMssMCB.numTxAntennas * gMmwMssMCB.numRxAntennas);
    params->numRangeBins = gMmwMssMCB.numRangeBins;
    params->numChirpsPerFrame = gMmwMssMCB.frameCfg.h_NumOfBurstsInFrame * gMmwMssMCB.frameCfg.h_NumOfChirpsInBurst;
    params->numDopplerChirpsPerFrame = params->numChirpsPerFrame/params->numTxAntennas;

    if ((params->numTxAntennas == 1) && (gMmwMssMCB.frameCfg.h_NumOfBurstsInFrame !=1))
    {
        retVal = DPC_OBJECTDETECTION_EINVAL_CFG;
        goto exit;
    }
    if ((params->numTxAntennas == 1) && (gMmwMssMCB.isBpmEnabled))
    {
        retVal = DPC_OBJECTDETECTION_EINVAL_CFG;
        goto exit;
    }

    if (params->enableMajorMotion)
    {
        params->numDopplerChirpsPerProc = params->numDopplerChirpsPerFrame;
    }
    else
    {
        params->numDopplerChirpsPerProc = params->numFramesPerMinorMotProc * params->numMinorMotionChirpsPerFrame;
    }

    params->isBpmEnabled = 0;//gMmwMssMCB.isBpmEnabled;
    /* windowing */
    params->ADCBufData.dataProperty.numRxAntennas = (uint8_t) gMmwMssMCB.numRxAntennas;
    params->ADCBufData.dataSize = gMmwMssMCB.profileComCfg.h_NumOfAdcSamples * params->ADCBufData.dataProperty.numRxAntennas * 4 ;
    params->ADCBufData.dataProperty.numAdcSamples = gMmwMssMCB.profileComCfg.h_NumOfAdcSamples;

    if (!gMmwMssMCB.oneTimeConfigDone)
    {
        mathUtils_genWindow((uint32_t *)params->window,
                            (uint32_t) params->ADCBufData.dataProperty.numAdcSamples,
                            params->windowSize/sizeof(uint32_t),
                            DPC_DPU_RANGEPROC_FFT_WINDOW_TYPE,
                            DPC_OBJDET_QFORMAT_RANGE_FFT);
    }
    params->rangeFFTtuning.fftOutputDivShift = 2;
    params->rangeFFTtuning.numLastButterflyStagesToScale = 0; /* no scaling needed as ADC is 16-bit and we have 8 bits to grow */

    params->rangeFftSize = mathUtils_pow2roundup(params->ADCBufData.dataProperty.numAdcSamples);

    bytesPerRxChan = params->ADCBufData.dataProperty.numAdcSamples * sizeof(uint16_t);
    bytesPerRxChan = (bytesPerRxChan + 15) / 16 * 16;

    for (index = 0; index < SYS_COMMON_NUM_RX_CHANNEL; index++)
    {
        params->ADCBufData.dataProperty.rxChanOffset[index] = index * bytesPerRxChan;
    }

    params->ADCBufData.dataProperty.interleave = DPIF_RXCHAN_NON_INTERLEAVE_MODE;

    // Data Input EDMA
    pHwConfig->edmaInCfg.dataIn.channel         = DPC_OBJDET_DPU_RANGEPROC_EDMAIN_CH; //1
    pHwConfig->edmaInCfg.dataIn.channelShadow[0]   = DPC_OBJDET_DPU_RANGEPROC_EDMAIN_SHADOW_PING; //64
    pHwConfig->edmaInCfg.dataIn.channelShadow[1]   = DPC_OBJDET_DPU_RANGEPROC_EDMAIN_SHADOW_PONG; //65
    pHwConfig->edmaInCfg.dataIn.eventQueue      = DPC_OBJDET_DPU_RANGEPROC_EDMAIN_EVENT_QUE; //0
    pHwConfig->edmaInCfg.dataInSignature.channel         = DPC_OBJDET_DPU_RANGEPROC_EDMAIN_SIG_CH; //28
    pHwConfig->edmaInCfg.dataInSignature.channelShadow   = DPC_OBJDET_DPU_RANGEPROC_EDMAIN_SIG_SHADOW; //66
    pHwConfig->edmaInCfg.dataInSignature.eventQueue      = DPC_OBJDET_DPU_RANGEPROC_EDMAIN_SIG_EVENT_QUE; //0
    pHwConfig->intrObj = intrObj_rangeProc;

    // Data Output EDMA
    pHwConfig->edmaOutCfg.path[0].evtDecim.channel = DPC_OBJDET_DPU_RANGEPROC_EVT_DECIM_PING_CH; //30
    pHwConfig->edmaOutCfg.path[0].evtDecim.channelShadow[0] = DPC_OBJDET_DPU_RANGEPROC_EVT_DECIM_PING_SHADOW_0; //69
    pHwConfig->edmaOutCfg.path[0].evtDecim.channelShadow[1] = DPC_OBJDET_DPU_RANGEPROC_EVT_DECIM_PING_SHADOW_1; //70
    pHwConfig->edmaOutCfg.path[0].evtDecim.eventQueue = DPC_OBJDET_DPU_RANGEPROC_EVT_DECIM_PING_EVENT_QUE; //0

    pHwConfig->edmaOutCfg.path[1].evtDecim.channel = DPC_OBJDET_DPU_RANGEPROC_EVT_DECIM_PONG_CH; //32
    pHwConfig->edmaOutCfg.path[1].evtDecim.channelShadow[0] = DPC_OBJDET_DPU_RANGEPROC_EVT_DECIM_PONG_SHADOW_0; //73
    pHwConfig->edmaOutCfg.path[1].evtDecim.channelShadow[1] = DPC_OBJDET_DPU_RANGEPROC_EVT_DECIM_PONG_SHADOW_1; //74
    pHwConfig->edmaOutCfg.path[1].evtDecim.eventQueue = DPC_OBJDET_DPU_RANGEPROC_EVT_DECIM_PONG_EVENT_QUE; //0

    pHwConfig->edmaOutCfg.path[0].dataOutMinor.channel = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MINOR_PING_CH; //29
    pHwConfig->edmaOutCfg.path[0].dataOutMinor.channelShadow = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MINOR_PING_SHADOW; //68
    pHwConfig->edmaOutCfg.path[0].dataOutMinor.eventQueue = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MINOR_PING_EVENT_QUE; //0

    pHwConfig->edmaOutCfg.path[1].dataOutMinor.channel = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MINOR_PONG_CH; //31
    pHwConfig->edmaOutCfg.path[1].dataOutMinor.channelShadow = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MINOR_PONG_SHADOW; //72
    pHwConfig->edmaOutCfg.path[1].dataOutMinor.eventQueue = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MINOR_PONG_EVENT_QUE; //0

    pHwConfig->edmaOutCfg.path[0].dataOutMajor.channel = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MAJOR_PING_CH; //6
    pHwConfig->edmaOutCfg.path[0].dataOutMajor.channelShadow = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MAJOR_PING_SHADOW; //67
    pHwConfig->edmaOutCfg.path[0].dataOutMajor.eventQueue = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MAJOR_PING_EVENT_QUE; //0

    pHwConfig->edmaOutCfg.path[1].dataOutMajor.channel = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MAJOR_PONG_CH; //7
    pHwConfig->edmaOutCfg.path[1].dataOutMajor.channelShadow = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MAJOR_PONG_SHADOW; //71
    pHwConfig->edmaOutCfg.path[1].dataOutMajor.eventQueue = DPC_OBJDET_DPU_RANGEPROC_EDMAOUT_MAJOR_PONG_EVENT_QUE; //0


    /* Radar cube compression */
    params->isCompressionEnabled = gMmwMssMCB.cliCompressionCfg.enabled;
    if (params->isCompressionEnabled)
    {
        params->compressCfg.compressionFactor = (uint8_t) (1./gMmwMssMCB.cliCompressionCfg.compressionRatio);
        params->compressCfg.numComplexElements = 2; //2 complex16 range bins
    }

    /* Radar cube Major Motion*/
    if (params->enableMajorMotion)
    {
        gMmwMssMCB.radarCube[0].dataSize = params->numRangeBins * params->numVirtualAntennas * sizeof(cmplx16ReIm_t) * params->numDopplerChirpsPerProc;
        if (params->isCompressionEnabled)
        {
            gMmwMssMCB.radarCube[0].dataSize = gMmwMssMCB.radarCube[0].dataSize / params->compressCfg.compressionFactor;
        }
        gMmwMssMCB.radarCube[0].data  = (cmplx16ImRe_t *) DPC_ObjDet_MemPoolAlloc(&gMmwMssMCB.L3RamObj,
                                                                               gMmwMssMCB.radarCube[0].dataSize,
                                                                               sizeof(uint32_t));
        if(gMmwMssMCB.radarCube[0].data == NULL)
        {
            retVal = DPC_OBJECTDETECTION_ENOMEM__L3_RAM_RADAR_CUBE;
            goto exit;
        }
    }
    else
    {
        gMmwMssMCB.radarCube[0].data  = NULL;
        gMmwMssMCB.radarCube[0].dataSize = 0;
    }
    gMmwMssMCB.radarCube[0].datafmt = DPIF_RADARCUBE_FORMAT_6;
    rangeProcDpuCfg.hwRes.radarCube = gMmwMssMCB.radarCube[0];

    /* Radar cube Minor Motion*/
    if (params->enableMinorMotion)
    {
        gMmwMssMCB.radarCube[1].dataSize = params->numRangeBins * params->numVirtualAntennas * sizeof(cmplx16ReIm_t) * params->numDopplerChirpsPerProc;
        if (params->isCompressionEnabled)
        {
            gMmwMssMCB.radarCube[1].dataSize = gMmwMssMCB.radarCube[1].dataSize / params->compressCfg.compressionFactor;
        }
        gMmwMssMCB.radarCube[1].data  = (cmplx16ImRe_t *) DPC_ObjDet_MemPoolAlloc(&gMmwMssMCB.L3RamObj,
                                                                                     gMmwMssMCB.radarCube[1].dataSize,
                                                                                     sizeof(uint32_t));
        if(gMmwMssMCB.radarCube[1].data == NULL)
        {
            retVal = DPC_OBJECTDETECTION_ENOMEM__L3_RAM_RADAR_CUBE;
            goto exit;
        }

    }
    else
    {
        gMmwMssMCB.radarCube[1].data  = NULL;
        gMmwMssMCB.radarCube[1].dataSize = 0;
    }
    gMmwMssMCB.radarCube[1].datafmt = DPIF_RADARCUBE_FORMAT_6;
    rangeProcDpuCfg.hwRes.radarCubeMinMot = gMmwMssMCB.radarCube[1];

exit:
    return retVal;
}

/**
*  @b Description
*  @n
*    Based on the configuration, set up the Capon Beamforming DPU configurations
*/
int32_t CaponBeamforming_configParser()
{
    printf("Configuring Capon Beamforming (Parsing)\n");
    int32_t retVal = 0;
    CaponBeamforming2DHWA_HW_Resources *pHwConfig = &caponBeamformingCfg.hwRes;
    CaponBeamforming2DHWA_StaticConfig * params;

    /* Capon Beamforming DPU */
    pHwConfig = &caponBeamformingCfg.hwRes;
    params = &caponBeamformingCfg.staticCfg;

    memset((void *)&caponBeamformingCfg, 0, sizeof(CaponBeamforming2DHWA_Config));

    //printf("numUsedHwaParamSets : %d\n",gMmwMssMCB.numUsedHwaParamSets); //4

    params->numVirtualAntennas = 6;//gMmwMssMCB.numTxAntennas * gMmwMssMCB.numRxAntennas; //gMmwMssMCB.leparametreici;
    params->numSnapshots = 32;
    params->numAnglesToSampleAzimuth = 32; //gMmwMssMCB.numAnglesToSampleAzimuth;
    params->numAnglesToSampleElevation = 16; //gMmwMssMCB.numAnglesToSampleElevation;

    for(uint8_t i=0;i<params->numVirtualAntennas;i++)
    {
        params->antennaCoordinates[2*i]= gMmwMssMCB.antennaGeometryCfg.ant[i].col;
        params->antennaCoordinates[2*i+1]= gMmwMssMCB.antennaGeometryCfg.ant[i].row;
    }

    /**
    for(uint8_t i=0;i<2*params->numVirtualAntennas;i++)
    {
        printf("params->antennaCoordinates[%d] = %d\n", i, params->antennaCoordinates[i]);
    }**/

    /* hwi configuration */
    /* HWA configurations, not related to per test, common to all test */

    /* Setting up the paramset start index for the use of HWA */
    pHwConfig->hwaCfg.caponBeamforming2DParamSetStartIdx = 11;

    /* Setting up the DMA channel which will trigger the HWA on DMA trigger (value <= 15) */
    pHwConfig->hwaDmaTriggerSourceCaponSpectrum = 11;
    DebugP_assert(pHwConfig->hwaDmaTriggerSourceCaponSpectrum < 16);

    /* Setting up the bCnt value to skip arrays in between successive elevation bins */
    pHwConfig->bCnt = 2;

    /* edma configuration */
    pHwConfig->edmaCfg.edmaHandle  = gEdmaHandle[0];

    pHwConfig->intrObjCaponSpectrum = intrObj_CaponBeamforming;


    gMmwMssMCB.rearranged_intermediate_data = (int16_t *) DPC_ObjDet_MemPoolAlloc(&gMmwMssMCB.L3RamObj,
                                                                                   gMmwMssMCB.radarCube[0].dataSize,
                                                                                   sizeof(uint16_t));
    if(gMmwMssMCB.rearranged_intermediate_data == NULL)
    {
        printf("SKIPPED !!\n");
        retVal = DPC_OBJECTDETECTION_ENOMEM__L3_RAM_RADAR_CUBE;
        goto exit;
    }

    gMmwMssMCB.caponInputData = (int32_t *) DPC_ObjDet_MemPoolAlloc(&gMmwMssMCB.L3RamObj,
                                                                    2*MAX_NUM_SNAPSHOTS * MAX_NUM_TX_ANTENNA * MAX_NUM_RX_ANTENNA*sizeof(int32_t),
                                                                    sizeof(int32_t));
    if(gMmwMssMCB.caponInputData == NULL)
        {
            printf("SKIPPED !!\n");
            retVal = DPC_OBJECTDETECTION_ENOMEM__L3_RAM_RADAR_CUBE;
            goto exit;
        }

    gMmwMssMCB.caponSpectrum = (float *) DPC_ObjDet_MemPoolAlloc(&gMmwMssMCB.L3RamObj,
                                                                 MAX_ANGLES_AZIMUTH*MAX_ANGLES_ELEVATION*MAX_RANGE_BINS_SKIP*sizeof(float),
                                                                 sizeof(float));


    /* input/output data to Capon Beamforming 2D */
    //pHwConfig->caponBeamforming2DInputData = caponInputData;
    //pHwConfig->caponSpectrum = caponSpectrum;
    pHwConfig->caponBeamforming2DInputData = gMmwMssMCB.caponInputData;
    pHwConfig->caponSpectrum = gMmwMssMCB.caponSpectrum;


    /* Data Input EDMA */
    pHwConfig->edmaCfg.edmaIn.caponSpectrumChannel.channel              = DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_CH_CAPONSPECTRUM; //17
    pHwConfig->edmaCfg.edmaIn.caponSpectrumChannel.channelShadow        = DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_SHADOW_CAPONSPECTRUM; //75 conflit resolu (65 avant)
    pHwConfig->edmaCfg.edmaIn.caponSpectrumChannel.eventQueue           = DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_EVENT_QUE_CAPONSPECTRUM; //0

    /* Hot signature EDMA */
    pHwConfig->edmaCfg.edmaHotSig.caponSpectrumChannel.channel              = DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_SIG_CH_CAPONSPECTRUM; //33 conflit resolu (29 avant)
    pHwConfig->edmaCfg.edmaHotSig.caponSpectrumChannel.channelShadow        = DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_SIG_SHADOW_CAPONSPECTRUM; //77 conflit resolu (67 avant)
    pHwConfig->edmaCfg.edmaHotSig.caponSpectrumChannel.eventQueue           = DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAIN_SIG_EVENT_QUE_CAPONSPECTRUM; //0

    /* Data Output EDMA */
    pHwConfig->edmaCfg.edmaOut.caponSpectrumChannel.channel             = DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAOUT_CAPONSPECTRUM_CH; //8 //conflit resolu (7 avant)
    pHwConfig->edmaCfg.edmaOut.caponSpectrumChannel.channelShadow       = DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAOUT_CAPONSPECTRUM_SHADOW; //79 conflit resolu (69 avant)
    pHwConfig->edmaCfg.edmaOut.caponSpectrumChannel.eventQueue          = DPC_OBJDET_DPU_CAPONBEAMFORMING2D_EDMAOUT_CAPONSPECTRUM_EVENT_QUE; //0

    //uint32_t read = caponBeamformingCfg.hwRes.edmaCfg.edmaOut.caponSpectrumChannel.channel;
    //printf("edmaOut.caponSpectrumChannel.channel %d\n", read);

exit:
    return retVal;
}

/**
*  @b Description
*  @n
*        Function configuring range processing DPU
*/
void mmwDemo_rangeProcConfig()
{
    int32_t retVal = 0;
    uint8_t numUsedHwaParamSets;

    retVal = RangeProc_configParser();
    if (retVal < 0)
    {
        CLI_write("Error in setting up range profile:%d \n", retVal);
        DebugP_assert(0);
    }

    retVal = DPU_RangeProcHWA_config(gMmwMssMCB.rangeProcDpuHandle, &rangeProcDpuCfg);
    if (retVal < 0)
    {
        CLI_write("Error: RANGE DPU config return error:%d \n", retVal);
        DebugP_assert(0);
    }

    /* Get number of used HWA param sets by this DPU */
    retVal = DPU_RangeProcHWA_GetNumUsedHwaParamSets(gMmwMssMCB.rangeProcDpuHandle, &numUsedHwaParamSets);
    if (retVal < 0)
    {
        CLI_write("Error: RANGE DPU return error:%d \n", retVal);
        DebugP_assert(0);
    }

    /* Update number of used HWA param sets */
    gMmwMssMCB.numUsedHwaParamSets += numUsedHwaParamSets;
    printf("mmwDemo_rangeProcConfig() finished successfully\n");
}

/**
*  @b Description
*  @n
*        Function configuring range processing DPU
*/
void mmwDemo_CaponBeamformingProcConfig()
{
    int32_t retVal = 0;

    memset((void*) &caponBeamformingCfg, 0, sizeof(CaponBeamforming2DHWA_Config));
    retVal = CaponBeamforming_configParser();

    if (retVal < 0)
    {
        CLI_write("Error in setting up Capon Beamforming:%d \n", retVal);
        DebugP_assert(0);
    }
    int length = caponBeamformingCfg.staticCfg.numAnglesToSampleAzimuth*caponBeamformingCfg.staticCfg.numAnglesToSampleElevation;
    gMmwMssMCB.caponSpectrumLength = length*sizeof(float);

    printf("Configuring Capon Beamforming applying config\n");
    //retVal = CaponBeamforming2DHWA_config(gMmwMssMCB.caponBeamformingHandle, &caponBeamformingCfg);
    if (retVal < 0)
    {
        CLI_write("Error: Capon Beamforming config return error:%d \n", retVal);
        DebugP_assert(0);
    }
    printf("mmwDemo_CaponBeamformingProcConfig() finished successfully\n");
}


/**
*  @b Description
*  @n
*        Function initiliazing all indvidual DPUs
*/
void DPC_Init()
{
    /* hwa, edma, and DPU initialization*/

    /* Register Frame Start Interrupt */
    if(mmwDemo_registerFrameStartInterrupt() != 0){
        CLI_write("Error: Failed to register frame start interrupts\n");
        DebugP_assert(0);
    }
/* For debugging purposes*/
#if 0
    if(mmwDemo_registerChirpAvailableInterrupts() != 0){
        CLI_write("Failed to register chirp available interrupts\n");
        DebugP_assert(0);
    }
    mmwDemo_registerChirpInterrupt();
    mmwDemo_registerBurstInterrupt();
#endif
    int32_t status = SystemP_SUCCESS;

    /* Shared memory pool */
    gMmwMssMCB.L3RamObj.cfg.addr = (void *)&gMmwL3[0];
    gMmwMssMCB.L3RamObj.cfg.size = sizeof(gMmwL3);

    /* Local memory pool */
    gMmwMssMCB.CoreLocalRamObj.cfg.addr = (void *)&gMmwCoreLocMem[0];
    gMmwMssMCB.CoreLocalRamObj.cfg.size = sizeof(gMmwCoreLocMem);
/* For debugging purposes*/
#if 0
    /* Memory pool for the tracker */
    HeapP_construct(&gMmwMssMCB.CoreLocalTrackerHeapObj, (void *) gMmwCoreLocMem2, MMWDEMO_OBJDET_CORE_LOCAL_MEM2_SIZE);

    /* Memory pool for the feature extraction */
    featExtract_heapConstruct();
#endif

    hwaHandle = HWA_open(0, NULL, &status);
    if (hwaHandle == NULL)
    {
        CLI_write("Error: Unable to open the HWA Instance err:%d\n", status);
        DebugP_assert(0);
    }

    rangeProc_dpuInit();
    //caponBeamforming_dpuInit();
}


/**
*  @b Description
*  @n

*        Function configuring all DPUs
*/
void DPC_Config()
{

    int32_t retVal;

    /*TODO Cleanup: MMWLPSDK-237*/
    
    DPC_ObjDet_MemPoolReset(&gMmwMssMCB.L3RamObj);
    DPC_ObjDet_MemPoolReset(&gMmwMssMCB.CoreLocalRamObj);
    DPC_ObjDet_HwaDmaTrigSrcChanPoolReset(&gMmwMssMCB.HwaDmaChanPoolObj);
    DPC_ObjDet_HwaWinRamMemoryPoolReset(&gMmwMssMCB.HwaWinRamMemoryPoolObj);




    #if (CLI_REMOVAL == 0)
    if (gMmwMssMCB.adcDataSourceCfg.source == 1)
    {
        gMmwMssMCB.dpcObjIndOut = (DPIF_PointCloudRngAzimElevDopInd *) DPC_ObjDet_MemPoolAlloc(&gMmwMssMCB.L3RamObj,
                                                                                           MAX_NUM_DETECTIONS * sizeof(DPIF_PointCloudRngAzimElevDopInd),
                                                                                           sizeof(uint32_t));
        if (gMmwMssMCB.dpcObjIndOut == NULL)
        {
            CLI_write("DPC configuration: memory allocation failed\n");
            DebugP_assert(0);
        }
    }
    #endif

    /* Select active antennas from available antennas and calculate number of antennas rows and columns */
    MmwDemo_calcActiveAntennaGeometry();

    /* Angle dimension */
    if ((gMmwMssMCB.numAntRow > 1) && (gMmwMssMCB.numAntCol > 1))
    {
        gMmwMssMCB.angleDimension = 2;
    }
    else if ((gMmwMssMCB.numAntRow == 1) && (gMmwMssMCB.numAntCol > 1))
    {
        gMmwMssMCB.angleDimension = 1;
    }
    else
    {
        gMmwMssMCB.angleDimension = 0;
    }

    /* Configure DPUs */
    gMmwMssMCB.numUsedHwaParamSets = 0;


    mmwDemo_rangeProcConfig();
    mmwDemo_CaponBeamformingProcConfig();

    /*Allocate memory for capon Spectrum 3D Heatmap */
    gMmwMssMCB.caponSpectrum3DHeatmap = (float *) DPC_ObjDet_MemPoolAlloc(&gMmwMssMCB.L3RamObj,
                                                                          10*caponBeamformingCfg.staticCfg.numAnglesToSampleAzimuth*caponBeamformingCfg.staticCfg.numAnglesToSampleElevation*sizeof(float),
                                                                          sizeof(uint32_t));
    if (gMmwMssMCB.caponSpectrum3DHeatmap == NULL)
    {
        CLI_write("DPC configuration: memory allocation failed\n");
        DebugP_assert(0);
    }


    if(gMmwMssMCB.measureRxChannelBiasCliCfg.enabled)
    {
        retVal = mmwDemo_rangeBiasRxChPhaseMeasureConfig();
        if (retVal != 0)
        {
            CLI_write("DPC configuration: Invalid Rx channel compensation procedure configuration \n");
            DebugP_assert(0);
        }
    }

    if (!gMmwMssMCB.oneTimeConfigDone)
    {

        /* Report RAM usage */
        gMmwMssMCB.memUsage.CoreLocalRamUsage = DPC_ObjDet_MemPoolGetMaxUsage(&gMmwMssMCB.CoreLocalRamObj);
        gMmwMssMCB.memUsage.L3RamUsage = DPC_ObjDet_MemPoolGetMaxUsage(&gMmwMssMCB.L3RamObj);
        HeapP_getHeapStats(&gMmwMssMCB.CoreLocalTrackerHeapObj, &gMmwMssMCB.memUsage.trackerHeapStats);

        gMmwMssMCB.memUsage.L3RamTotal = gMmwMssMCB.L3RamObj.cfg.size;
        gMmwMssMCB.memUsage.CoreLocalRamTotal = gMmwMssMCB.CoreLocalRamObj.cfg.size;
    
        if(gMmwMssMCB.lowPowerMode == LOW_PWR_MODE_DISABLE)
        {
            DebugP_log(" ========== Memory Stats ==========\n");
            DebugP_log("%20s %12s %12s %12s\n", " ", "Size", "Used", "Free");

            DebugP_log("%20s %12d %12d %12d\n", "L3",
                      sizeof(gMmwL3),
                      gMmwMssMCB.memUsage.L3RamUsage,
                      sizeof(gMmwL3) - gMmwMssMCB.memUsage.L3RamUsage);

            DebugP_log("%20s %12d %12d %12d\n", "Local",
                      sizeof(gMmwCoreLocMem),
                      gMmwMssMCB.memUsage.CoreLocalRamUsage,
                      sizeof(gMmwCoreLocMem) - gMmwMssMCB.memUsage.CoreLocalRamUsage);
        }
    }
}

void print_list_int(int* list, int32_t size) {
    if (list == NULL || size <= 0) {
        printf("[]\n");
        return;
    }

    printf("size of int32_t : %d\n",sizeof(int32_t));
    printf("List size : %d\n", size);
    printf("[");

    for (int32_t i = 0; i < size; i++) {
        if (i > 0 && i % 10 == 0) {
            printf("\n ");
        }
        printf("%d", list[i]);
        if (i < size - 1) {
            printf(", ");
        }
    }
    printf("]\n");
}

void print_list_complex(cmplx16ImRe_t* list, int32_t size) {
    if (list == NULL || size <= 0) {
        printf("[]\n");
        return;
    }

    printf("size of int32_t : %d\n",sizeof(int32_t));
    printf("List size : %d\n", size);
    printf("[");

    for (int32_t i = 0; i < size; i++) {
        if (i > 0 && i % 10 == 0) {
            printf("\n ");
        }
        printf("%d + i%d", list[i].real, list[i].imag);
        if (i < size - 1) {
            printf(", ");
        }
    }
    printf("]\n");
}


void print_list_float(float* list, int32_t size) {
    if (list == NULL || size <= 0) {
        printf("[]\n");
        return;
    }

    printf("size of int32_t : %d\n",sizeof(int32_t));
    printf("List size : %d\n", size);
    printf("[");

    for (int32_t i = 0; i < size; i++) {
        if (i > 0 && i % 10 == 0) {
            printf("\n ");
        }
        printf("%f", list[i]);
        if (i < size - 1) {
            printf(", ");
        }
    }
    printf("]\n");
}

void rearrange_radar_cube(cmplx16ImRe_t* list, int16_t * output) {
    int32_t L = 64;  // ranges
    int32_t l = 6;   // antennas
    int32_t H = 32;  // chirps

    // Input: list est organisé comme (64, 6, 32) - [L][l][H] = [ranges][antennas][chirps]
    // Output: on veut (64, 32, 6, 2) - [L][H][l][2] = [ranges][chirps][antennas][real/imag]

    for (int32_t range_id = 0; range_id < L; range_id++) {
        for (int32_t antenna_id = 0; antenna_id < l; antenna_id++) {
            for (int32_t chirp_id = 0; chirp_id < H; chirp_id++) {
                // Index dans le tableau d'entrée: [range_id][antenna_id][chirp_id]
                int32_t input_idx = range_id * (l * H) + antenna_id * H + chirp_id;

                // Index dans le tableau de sortie: [range_id][chirp_id][antenna_id][real/imag]
                int32_t output_idx = (range_id * (H * l) + chirp_id * l + antenna_id) * 2;

                output[output_idx] = list[input_idx].real;
                output[output_idx + 1] = list[input_idx].imag;
            }
        }
    }
    return;
}

void get_x_range_from_rearranged_radar_cube(int16_t* rearranged_radar_cube_ptr, int range_id, int32_t * output) {
    int32_t l = 6;   // antennas
    int32_t H = 32;  // chirps

    // Input: list est organisé comme (64, 32, 6, 2) - [L][l][H][2] = [ranges][chirps][antennas][real/imag]
    // Output: on veut (32, 6, 2) - [H][l][2] = [chirps][antennas][real/imag].
    // Comme faire List[range_id] en python

    memset((int32_t*)output, 0, sizeof(int32_t)*sizeof(2*MAX_NUM_SNAPSHOTS * MAX_NUM_TX_ANTENNA * MAX_NUM_RX_ANTENNA));

    int32_t index = 0;

    for (int32_t chirp_id = 0; chirp_id < H; chirp_id++) {
        for (int32_t antenna_id = 0; antenna_id < l; antenna_id++) {
            // Index dans le cube réarrangé: [range_id][chirp_id][antenna_id][real/imag]
            int32_t cube_idx = (range_id * (H * l) + chirp_id * l + antenna_id) * 2;

            output[index] = rearranged_radar_cube_ptr[cube_idx];      // real
            output[index + 1] = rearranged_radar_cube_ptr[cube_idx + 1];  // imag
            index += 2;
        }
    }
    //printf("HERE! \n");
    return;
}

/**
 *  @b Description
 *  @n  DPC processing chain execute function.
 *
 */
void DPC_Execute(){
    int32_t retVal;
    int32_t errCode = 0;
    int32_t i;
    DPU_RangeProcHWA_OutParams outParms;

    #if (SPI_ADC_DATA_STREAMING==1)
    MCSPI_Transaction   spiTransaction;
    int32_t             transferOK;
    uint32_t totalSizeToTfr,tempSize;
    uint8_t count;
    #endif
    uint8_t enableMajorMotion;
    uint8_t enableMinorMotion;
    DPC_ObjectDetection_ExecuteResult *result = &gMmwMssMCB.dpcResult;

    volatile uint32_t               startCycle, cycleCount;
    /* give initial trigger for the first frame */
    printf("Executing DPC...\n");
    errCode = DPU_RangeProcHWA_control(gMmwMssMCB.rangeProcDpuHandle,
                 DPU_RangeProcHWA_Cmd_triggerProc, NULL, 0);
    if(errCode < 0)
    {
        CLI_write("Error: Range control execution failed [Error code %d]\n", errCode);
    }

    if (gMmwMssMCB.sigProcChainCfg.motDetMode == 1)
    {
        enableMajorMotion = 1;
        enableMinorMotion = 0;
    }
    else if (gMmwMssMCB.sigProcChainCfg.motDetMode == 3)
    {
        enableMajorMotion = 1;
        enableMinorMotion = 1;
    }
    else
    {
        enableMajorMotion = 0;
        enableMinorMotion = 1;
    }
    if (enableMajorMotion)
    {
        result->rngAzHeatMap[MMW_DEMO_MAJOR_MODE] = (uint32_t *) gMmwMssMCB.detMatrix.data;
    }
    else
    {
        result->rngAzHeatMap[MMW_DEMO_MAJOR_MODE] = NULL;
    }
    if (enableMinorMotion)
    {
        result->rngAzHeatMap[MMW_DEMO_MINOR_MODE] = (uint32_t *) gMmwMssMCB.detMatrix.data;
    }
    else
    {
        result->rngAzHeatMap[MMW_DEMO_MINOR_MODE] = NULL;
    }

    //result->objOut = gMmwMssMCB.dpcObjOut;
    //result->objOutSideInfo = gMmwMssMCB.dpcObjSideInfo;
    result->caponBf3DHeatmap = gMmwMssMCB.caponSpectrum3DHeatmap;

    // A retirer
    result->rngDopplerHeatMap = (uint32_t *) gMmwMssMCB.detMatrix.data;

    /* Send signal to CLI task that this is ready */
    SemaphoreP_post(&gMmwMssMCB.dpcTaskConfigDoneSemHandle);

    int iteration_number = 0;
    while(true){
        //Wait for tlv to be sent starting on the second iteration loop
        if (iteration_number>0) {
            SemaphoreP_pend(&gMmwMssMCB.tlvTaskDoneSemHandle, SystemP_WAIT_FOREVER);
        }
        startCycle = CycleCounterP_getCount32();

        // Range Proc DPU
        memset((void *)&outParms, 0, sizeof(DPU_RangeProcHWA_OutParams));

        printf("DPU_RangeProcHWA_process()...\n");
        retVal = DPU_RangeProcHWA_process(gMmwMssMCB.rangeProcDpuHandle, &outParms);


        if(retVal != 0){

            CLI_write("DPU_RangeProcHWA_process failed with error code %d", retVal);
            DebugP_assert(0);
        }


        //printf("Reading temperature \n");
        // Read the temperature
        MMWave_getTemperatureReport(&tempStats);
        /* Chirping finished start interframe processing */
        //printf("Interframe start processing \n");
        gMmwMssMCB.stats.interFrameStartTimeStamp = Cycleprofiler_getTimeStamp();
        gMmwMssMCB.stats.chirpingTime_us = (gMmwMssMCB.stats.interFrameStartTimeStamp - gMmwMssMCB.stats.frameStartTimeStamp)/FRAME_REF_TIMER_CLOCK_MHZ;


        if((gMmwMssMCB.lowPowerMode == LOW_PWR_MODE_ENABLE) || (gMmwMssMCB.lowPowerMode == LOW_PWR_TEST_MODE))
        {
            //Shutdown the FECSS after chirping
            // Retain FECSS Code Memory

            int32_t err;

            if(pgVersion==1)
            {
                PRCMSetSRAMRetention((PRCM_FEC_PD_SRAM_CLUSTER_2 | PRCM_FEC_PD_SRAM_CLUSTER_3), PRCM_SRAM_LPDS_RET);
            }
            else
            {
                PRCMSetSRAMRetention((PRCM_FEC_PD_SRAM_CLUSTER_1), PRCM_SRAM_LPDS_RET);
            }
            
            //Reset The FrameTimer for next frame
            HW_WR_REG32(CSL_APP_RCM_U_BASE + CSL_APP_RCM_BLOCKRESET2, 0x1c0);
            for(int i =0;i<10;i++)
            {
                test = PRCMSlowClkCtrGet();
            }
            HW_WR_REG32(CSL_APP_RCM_U_BASE + CSL_APP_RCM_BLOCKRESET2, 0x0);
            

            // MMW Closure in preparation for Low power state
            MMWave_stop(gMmwMssMCB.ctrlHandle,&err);
            MMWave_close(gMmwMssMCB.ctrlHandle,&err);
            MMWave_deinit(gMmwMssMCB.ctrlHandle,&err);
            /* As the Frame timer is reset, Capture the Inter Frame Start Time again */
            gMmwMssMCB.stats.interFrameStartTimeStamp = Cycleprofiler_getTimeStamp();
        }
        

         /* Procedure for range bias measurement and Rx channels gain/phase offset measurement */
        //printf("Measuring Bias Rx Channel Bias \n");
        if(gMmwMssMCB.measureRxChannelBiasCliCfg.enabled)
        {
                mmwDemo_rangeBiasRxChPhaseMeasure();
        }

        // Rearrange data
        rearrange_radar_cube(gMmwMssMCB.radarCube[0].data, gMmwMssMCB.rearranged_intermediate_data);

        // Perform Beamforming
        memset((float *)&gMmwMssMCB.caponSpectrum3DHeatmap[0], 0.0, gMmwMssMCB.caponSpectrumLength);
        int32_t length = gMmwMssMCB.caponSpectrumLength/sizeof(float);


        for (int8_t k=0; k<10; k++) {
            //printf("k*length = %d\n", k*length);
            if (k>=0) {
                get_x_range_from_rearranged_radar_cube(gMmwMssMCB.rearranged_intermediate_data, k, gMmwMssMCB.caponInputData);

                retVal = caponBeamforming2D_process(&caponBeamformingCfg, gMmwMssMCB.caponSpectrum);
                if(retVal < 0)
                {
                    DebugP_log("DEBUG: Capon Beamforming DPU process return error:%d \n", retVal);
                    DebugP_assert(0);
                }

                // Put the output of the proper beamformed layer inside the output object
                for (int32_t i=0; i<length; i++) {
                    gMmwMssMCB.caponSpectrum3DHeatmap[i + k*length] = gMmwMssMCB.caponSpectrum[2*i]; //prendre que les parties réelles
                }

            }
        }

        #if (CLI_REMOVAL == 0)
        if (gMmwMssMCB.adcDataSourceCfg.source == 2)
        {
            ClockP_sleep(1);
        }
        #endif
        
        /* Give initial trigger for the next frame */
        retVal = DPU_RangeProcHWA_control(gMmwMssMCB.rangeProcDpuHandle,
                    DPU_RangeProcHWA_Cmd_triggerProc, NULL, 0);
        if(retVal < 0)
        {
            CLI_write("Error: DPU_RangeProcHWA_control failed with error code %d", retVal);
            DebugP_assert(0);
        }

        /* Interframe processing finished */
        gMmwMssMCB.stats.interFrameEndTimeStamp = Cycleprofiler_getTimeStamp();
        gMmwMssMCB.outStats.interFrameProcessingTime = (gMmwMssMCB.stats.interFrameEndTimeStamp - gMmwMssMCB.stats.interFrameStartTimeStamp)/FRAME_REF_TIMER_CLOCK_MHZ;

        /* Trigger UART task to send TLVs to host */
        SemaphoreP_post(&gMmwMssMCB.tlvSemHandle);
        cycleCount = CycleCounterP_getCount32()-startCycle;
        DebugP_log("DPC loop task time = CPU cycles = %d !!!\r\n", cycleCount);
        iteration_number++;
    }
}
