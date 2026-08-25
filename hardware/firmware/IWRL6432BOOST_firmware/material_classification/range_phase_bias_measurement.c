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
#include <control/mmwave/mmwave.h>
#include "source/mmw_cli.h"
#include "ti_drivers_config.h"
#include "ti_drivers_open_close.h"
#include "ti_board_open_close.h"
#include "ti_board_config.h"
#include <FreeRTOS.h>
#include <task.h>
#include <semphr.h>

#include "source/mmwave_demo.h"
#include "source/dpc/dpc.h"

#define MMWDEMO_RFPARSER_SPEED_OF_LIGHT_IN_METERS_PER_SEC (3e8)
extern MmwDemo_MSS_MCB gMmwMssMCB;

/**
 *  @b Description
 *  @n
 *      The function initializes parameters for the measurement procedure for rx channel compensation
 *
 *
 *  @retval   None
 *
 */
int32_t  mmwDemo_rangeBiasRxChPhaseMeasureConfig ()
{
    int32_t retVal = 0;
    int32_t i;
    float slope;
    float targetDistance = gMmwMssMCB.measureRxChannelBiasCliCfg.targetDistance;
    float searchWinSize= gMmwMssMCB.measureRxChannelBiasCliCfg.searchWinSize;


    //Check for CLI configuration, major mode, clutter removal disabled, TDM MIMO mode, all antennas active: 2Tx 3Rx, ...
    if ((!gMmwMssMCB.enableMajorMotion) ||
        (gMmwMssMCB.staticClutterRemovalEnable) ||
        (!gMmwMssMCB.isBpmEnabled) ||
        (gMmwMssMCB.numTxAntennas != SYS_COMMON_NUM_TX_ANTENNAS) ||
        (gMmwMssMCB.numRxAntennas != SYS_COMMON_NUM_RX_CHANNEL))
    {
        retVal = -1;
    }

    if (retVal < 0)
    {
        goto exit;
    }

    /* Range step (meters/bin)*/
    slope = (float)(gMmwMssMCB.chirpSlope * 1.e12);
    gMmwMssMCB.measureRxChannelBiasParams.rangeStep = (MMWDEMO_RFPARSER_SPEED_OF_LIGHT_IN_METERS_PER_SEC * (gMmwMssMCB.adcSamplingRate * 1.e6)) /
                                                      (2.f * slope * (2*gMmwMssMCB.numRangeBins));
    gMmwMssMCB.measureRxChannelBiasParams.oneOverRangeStep = 1 / gMmwMssMCB.measureRxChannelBiasParams.rangeStep;


    /* Target position in bins */
    gMmwMssMCB.measureRxChannelBiasParams.trueBinPosition = targetDistance  * gMmwMssMCB.measureRxChannelBiasParams.oneOverRangeStep;

    /* Find the search range for the peak of the target at the bore sight */
    i = (int32_t) ((targetDistance - searchWinSize/2.) * gMmwMssMCB.measureRxChannelBiasParams.oneOverRangeStep + 0.5);
    if (i < 1)
    {
        i = 1;
    }
    gMmwMssMCB.measureRxChannelBiasParams.rngSearchLeftIdx = (int16_t) i;
    i = (int32_t) ((targetDistance + searchWinSize/2.) * gMmwMssMCB.measureRxChannelBiasParams.oneOverRangeStep + 0.5);
    gMmwMssMCB.measureRxChannelBiasParams.rngSearchRightIdx = (int16_t) i;

exit:
    return retVal;
}

/**
 *  @b Description
 *  @n
 *      Computes the range bias and rx phase compensation coefficients
 *      Sensor must be configured in 2Tx BPM-MIMO mode
 *
 *  @retval   None
 *
 */
void mmwDemo_rangeBiasRxChPhaseMeasure ()
{
    DPIF_compRxChannelBiasFloatCfg *compRxChanCfg = &gMmwMssMCB.compRxChannelBiasCfgMeasureOut;
    cmplx16ImRe_t *symbolMatrix = (cmplx16ImRe_t *) gMmwMssMCB.radarCube[0].data; //Major motion

    cmplx16ImRe_t rxSym[SYS_COMMON_NUM_TX_ANTENNAS*SYS_COMMON_NUM_RX_CHANNEL];
    cmplx16ImRe_t *s1Ptr,*s2Ptr;
    cmplx16ImRe_t temp;
    int32_t bpmSign;
    float sumSqr, sumSqrMax;
    float xMagSq[SYS_COMMON_NUM_TX_ANTENNAS*SYS_COMMON_NUM_RX_CHANNEL] = {0};
    int32_t iMax;
    float xMagSqMin, xMagSqRootMin;
    float scal;
    float truePosition = gMmwMssMCB.measureRxChannelBiasParams.trueBinPosition;
    float rangeStep = gMmwMssMCB.measureRxChannelBiasParams.rangeStep;
    float y[3];
    float x[3];
    float estPeakPos;
    float estPeakVal;
    int32_t i, ind;
    int32_t txIdx, rxIdx;

    uint32_t numRxAntennas = gMmwMssMCB.numRxAntennas;
    uint32_t numTxAntennas = gMmwMssMCB.numTxAntennas;
    uint32_t numVirtualAntennas = numRxAntennas * numTxAntennas;
    uint32_t numRangeBins = gMmwMssMCB.numRangeBins;

    uint32_t numSymPerTxAnt = numRxAntennas * numRangeBins;
    uint32_t s1MatrixIndx, s2MatrixIndx;



    /**** Range calibration ****/
    iMax = gMmwMssMCB.measureRxChannelBiasParams.rngSearchLeftIdx;
    sumSqrMax = 0;
    for (i = gMmwMssMCB.measureRxChannelBiasParams.rngSearchLeftIdx; i <= gMmwMssMCB.measureRxChannelBiasParams.rngSearchRightIdx; i++)
    {
        sumSqr = 0.0;
        for (txIdx=0; txIdx < numTxAntennas; txIdx++)
        {
            bpmSign = 1-2*(txIdx & 0x1);
            for (rxIdx=0; rxIdx < numRxAntennas; rxIdx++)
            {
                s1MatrixIndx = 0 * numSymPerTxAnt + rxIdx * numRangeBins + i;
                s2MatrixIndx = 1 * numSymPerTxAnt + rxIdx * numRangeBins + i;
                s1Ptr = (cmplx16ImRe_t *) &symbolMatrix[s1MatrixIndx];
                s2Ptr = (cmplx16ImRe_t *) &symbolMatrix[s2MatrixIndx];
                temp.real  = s1Ptr->real + bpmSign * s2Ptr->real;
                temp.imag  = s1Ptr->imag + bpmSign * s2Ptr->imag;
                sumSqr += (float) temp.real * (float) temp.real +
                          (float) temp.imag * (float) temp.imag;
            }
        }

        if (sumSqr > sumSqrMax)
        {
            sumSqrMax = sumSqr;
            iMax = i;
        }
    }

    /* Fine estimate of the peak position using quadratic fit */
    ind = 0;
    for (i = iMax-1; i <= iMax+1; i++)
    {
        sumSqr = 0.0;
        for (txIdx=0; txIdx < numTxAntennas; txIdx++)
        {
            bpmSign = 1-2*(txIdx & 0x1);;
            for (rxIdx=0; rxIdx < numRxAntennas; rxIdx++)
            {
                s1MatrixIndx = 0 * numSymPerTxAnt + rxIdx * numRangeBins + i;
                s2MatrixIndx = 1 * numSymPerTxAnt + rxIdx * numRangeBins + i;
                s1Ptr = (cmplx16ImRe_t *) &symbolMatrix[s1MatrixIndx];
                s2Ptr = (cmplx16ImRe_t *) &symbolMatrix[s2MatrixIndx];
                temp.real  = s1Ptr->real + bpmSign * s2Ptr->real;
                temp.imag  = s1Ptr->imag + bpmSign * s2Ptr->imag;
                sumSqr += (float) temp.real * (float) temp.real +
                          (float) temp.imag * (float) temp.imag;
            }
        }
        y[ind] = sqrtf(sumSqr);
        x[ind] = (float)i;
        ind++;
    }
    rangeBiasRxChPhaseMeasure_quadfit(x, y, &estPeakPos, &estPeakVal);
    compRxChanCfg->rangeBias = (estPeakPos - truePosition) * rangeStep;

    /*** Calculate Rx channel phase/gain compensation coefficients ***/
    for (txIdx = 0; txIdx < numTxAntennas; txIdx++)
    {
        for (rxIdx = 0; rxIdx < numRxAntennas; rxIdx++)
        {
            bpmSign = 1-2*(txIdx & 0x1);;
            i = txIdx * numRxAntennas + rxIdx;
            s1MatrixIndx = 0 * numSymPerTxAnt + rxIdx * numRangeBins + iMax;
            s2MatrixIndx = 1 * numSymPerTxAnt + rxIdx * numRangeBins + iMax;
            s1Ptr = (cmplx16ImRe_t *) &symbolMatrix[s1MatrixIndx];
            s2Ptr = (cmplx16ImRe_t *) &symbolMatrix[s2MatrixIndx];
            temp.real  = s1Ptr->real + bpmSign * s2Ptr->real;
            temp.imag  = s1Ptr->imag + bpmSign * s2Ptr->imag;
            rxSym[i] = temp;
            xMagSq[i] = (float) rxSym[i].real * (float) rxSym[i].real +
                        (float) rxSym[i].imag * (float) rxSym[i].imag;
        }
    }
    xMagSqMin = xMagSq[0];
    for (i = 1; i < numVirtualAntennas; i++)
    {
        if (xMagSq[i] < xMagSqMin)
        {
            xMagSqMin = xMagSq[i];
        }
    }

    if (xMagSqMin > 0.)
    {
        xMagSqRootMin = sqrt(xMagSqMin);
        for (txIdx=0; txIdx < numTxAntennas; txIdx++)
        {
            for (rxIdx=0; rxIdx < numRxAntennas; rxIdx++)
            {
                float temp;
                i = txIdx * numRxAntennas + rxIdx;
                scal = 1./ xMagSq[i] * xMagSqRootMin;

                temp = scal * rxSym[i].real;
                compRxChanCfg->rxChPhaseComp[2*i] = temp;

                temp = -scal * rxSym[i].imag;
                compRxChanCfg->rxChPhaseComp[2*i+1] = temp;
            }
        }
    }
    else
    {
        for (i=0; i < (2*numVirtualAntennas); i++)
        {
                compRxChanCfg->rxChPhaseComp[i] = 0.;
        }
    }
}