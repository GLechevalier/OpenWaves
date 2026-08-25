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
#include <string.h>
#include <stdio.h>

#include "source/mmwave_demo.h"
#include "mmw_flash_cal.h"
#include "source/mmw_res.h"
#include "source/mmw_cli.h"
#include <mmwavelink/include/rl_device.h>
#include <mmwavelink/include/rl_sensor.h>
#include "source/calibrations/factory_cal.h"
#include "source/mmwave_control/monitors.h"

/* Calibration Data Save/Restore defines */
#define MMWDEMO_CALIB_STORE_MAGIC            (0x7CB28DF9U)

extern MmwDemo_MSS_MCB gMmwMssMCB;

#if (ENABLE_MONITORS==1)
/*! @brief  RF Monitor LB result during factory calibration */
volatile MmwDemo_Mon_Result rfMonResFactCal = {0};
/* Flag to indicate status of storing monitor results during factory calibration */
uint8_t rfMonSemFactCalFlag = 0;
#endif

MmwDemo_calibData gFactoryCalibDataStorage __attribute__((aligned(8))) = {0};

/**
 *  @b Description
 *  @n
 *      This function reads calibration data from flash and send it to front end
 *
 *  @param[in]  ptrCalibData         Pointer to Calibration data
 *
 *  @retval
 *      Success -   0
 *  @retval
 *      Error   -   <0
 */
static int32_t MmwDemo_calibRestore(MmwDemo_calibData  *ptrCalibData)
{
    int32_t    retVal = 0;
    uint32_t   flashOffset;

    /* Get Flash Offset */
    flashOffset = gMmwMssMCB.factoryCalCfg.flashOffset;

    /* Read calibration data */
    if(mmwDemo_flashRead(flashOffset, (uint8_t *)ptrCalibData, sizeof(MmwDemo_calibData) )< 0)
    {
        /* Error: Failed to read from Flash */
        CLI_write ("Error: MmwDemo failed when reading Factory calibration data from flash.\r\n");
        return -1;
    }

    /* Validate Calib data Magic number */
    if(ptrCalibData->magic != MMWDEMO_CALIB_STORE_MAGIC)
    {
        /* Header validation failed */
        CLI_write ("Error: MmwDemo Factory calibration data header validation failed.\r\n");
        return -1;
    }

    return retVal;
}

/**
 *  @b Description
 *  @n
 *      This function retrieves the calibration data from front end and saves it in flash.
 *
 *  @param[in]  ptrCalibrationData      Pointer to Calibration data
 *
 *  @retval
 *      Success -   0
 *  @retval
 *      Error   -   <0
 */
static int32_t MmwDemo_calibSave(MmwDemo_calibData  *ptrCalibrationData)
{
    uint32_t                flashOffset;
    int32_t                 retVal = 0;

    /* Calculate the read size in bytes */
    flashOffset = gMmwMssMCB.factoryCalCfg.flashOffset;

    /* Flash calibration data */
    retVal = mmwDemo_flashWrite(flashOffset, (uint8_t *)ptrCalibrationData, sizeof(MmwDemo_calibData));
    if(retVal < 0)
    {
        /* Flash write failed */
        CLI_write ("Error: MmwDemo failed flashing calibration data with error[%d].\n", retVal);
    }

    return retVal;
}

/**
 *  @b Description
 *  @n
 *      This function performs factory calibration and saves it in flash
 *
 *  @retval
 *      Success -   0
 *  @retval
 *      Error   -   <0
 */
/* Note: In realtime applications, factory calibration is a one-time activity and users are expected to perform this only once */
int32_t mmwDemo_factoryCal(void)
{
    uint16_t         calRfFreq = 0U;
    MMWave_calibCfg  factoryCalCfg = {0U};
    int32_t          retVal = SystemP_SUCCESS;
    int32_t          errCode;
    MMWave_ErrorLevel   errorLevel;
    int16_t          mmWaveErrorCode;
    int16_t          subsysErrorCode;

    /* Enable sensor boot time calibration: */
    factoryCalCfg.isFactoryCalEnabled = true;

    /*
    * @brief  FECSS RFS Boot calibration control:
    * | bits [0] | RESERVED
    * | bits [1] | VCO calibration ON/OFF control
    * | bits [2] | PD calibration ON/OFF control
    * | bits [3] | LODIST calibration ON/OFF control
    * | bits [4] | RESERVED 
    * | bits [5] | RX IFA calibration ON/OFF control
    * | bits [6] | RX Gain calibration ON/OFF control
    * | bits [7] | TX power calibration ON/OFF control
    */
    /* As part of Factory Calibration, enable all calibrations except RX IFA calibration */
    factoryCalCfg.fecRFFactoryCalCmd.h_CalCtrlBitMask = 0xCEU;
    factoryCalCfg.fecRFFactoryCalCmd.c_MiscCalCtrl = 0x0U;
    factoryCalCfg.fecRFFactoryCalCmd.c_CalRxGainSel = gMmwMssMCB.factoryCalCfg.rxGain;
    factoryCalCfg.fecRFFactoryCalCmd.c_CalTxBackOffSel[0] = gMmwMssMCB.factoryCalCfg.txBackoffSel;
    factoryCalCfg.fecRFFactoryCalCmd.c_CalTxBackOffSel[1] = gMmwMssMCB.factoryCalCfg.txBackoffSel;

    /* Calculate Calibration Rf Frequency. Use Center frequency of the bandwidth(being used in demo) for calibration */
#if SOC_XWRL64XX
    calRfFreq = (gMmwMssMCB.profileTimeCfg.w_ChirpRfFreqStart) + \
                ((((gMmwMssMCB.chirpSlope * 256.0)/300) * (gMmwMssMCB.profileComCfg.h_ChirpRampEndTime * 0.1)) / 2);
    factoryCalCfg.fecRFFactoryCalCmd.xh_CalRfSlope = 0x4Du; /* 2.2Mhz per uSec*/
#else
    calRfFreq = (gMmwMssMCB.profileTimeCfg.w_ChirpRfFreqStart) + \
                ((((gMmwMssMCB.chirpSlope * 256.0)/400) * (gMmwMssMCB.profileComCfg.h_ChirpRampEndTime * 0.1)) / 2);
    factoryCalCfg.fecRFFactoryCalCmd.xh_CalRfSlope = 0x3Au; /* 2.2Mhz per uSec*/
#endif

    factoryCalCfg.fecRFFactoryCalCmd.h_CalRfFreq = calRfFreq;
    if(gMmwMssMCB.channelCfg.h_TxChCtrlBitMask == 0x3)
    {
        factoryCalCfg.fecRFFactoryCalCmd.c_TxPwrCalTxEnaMask[0] = 0x3;
        factoryCalCfg.fecRFFactoryCalCmd.c_TxPwrCalTxEnaMask[1] = 0x1;
    }
    else 
    {
        if(gMmwMssMCB.channelCfg.h_TxChCtrlBitMask == 0x1)
        {
            factoryCalCfg.fecRFFactoryCalCmd.c_TxPwrCalTxEnaMask[0] = 0x1;
            factoryCalCfg.fecRFFactoryCalCmd.c_TxPwrCalTxEnaMask[1] = 0x1;
        }
        if(gMmwMssMCB.channelCfg.h_TxChCtrlBitMask == 0x2)
        {
            factoryCalCfg.fecRFFactoryCalCmd.c_TxPwrCalTxEnaMask[0] = 0x2;
            factoryCalCfg.fecRFFactoryCalCmd.c_TxPwrCalTxEnaMask[1] = 0x2;
        }
    }

    /* Check if the device is RF-Trimmed */
    if(gMmwMssMCB.factoryCalCfg.atecalibinEfuse == true)
    {
        /* If RF-Trimmed, no need to fetch the ATE calib data */ 
        factoryCalCfg.ptrAteCalibration = NULL;
        factoryCalCfg.isATECalibEfused  = true;
    }
    else
    {
        factoryCalCfg.ptrAteCalibration = NULL;
        factoryCalCfg.isATECalibEfused  = false;
        CLI_write("Error: Device is not RF-Trimmed!\n");
        MmwDemo_debugAssert (0);
    }

    /* If restore option is selected, Factory Calibration is not re-run and data is restored from Flash */ 
    if(gMmwMssMCB.factoryCalCfg.restoreEnable == 1U)
    {
        if(MmwDemo_calibRestore(&gFactoryCalibDataStorage) < 0)
        {
            CLI_write ("Error: MmwDemo failed restoring Factory Calibration data from flash.\r\n");
            MmwDemo_debugAssert (0);
        }

        /* Populate calibration data pointer. */
        factoryCalCfg.ptrFactoryCalibData = &gFactoryCalibDataStorage.calibData;

        /* Disable factory calibration. */
        factoryCalCfg.isFactoryCalEnabled = false;
    }

    retVal = MMWave_factoryCalibConfig(gMmwMssMCB.ctrlHandle, &factoryCalCfg, &errCode);
    if (retVal != SystemP_SUCCESS)
    {

        /* Error: Unable to perform boot calibration */
        MMWave_decodeError (errCode, &errorLevel, &mmWaveErrorCode, &subsysErrorCode);

        /* Error: Unable to initialize the mmWave control module */
        CLI_write ("Error: mmWave Control Initialization failed [Error code %d] [errorLevel %d] [mmWaveErrorCode %d] [subsysErrorCode %d]\n", errCode, errorLevel, mmWaveErrorCode, subsysErrorCode);
        if (mmWaveErrorCode == MMWAVE_ERFSBOOTCAL)
        {
            CLI_write ("Error: Factory Calibration failure\n");
        }
        else
        {
            CLI_write ("Error: Invalid Factory calibration arguments\n");
            MmwDemo_debugAssert (0);
        }
    }
#if (ENABLE_MONITORS==1)
          if(gMmwMssMCB.rfMonEnbl != 0)
        {
            rfMonSemFactCalFlag = RF_MON_FACT_CAL_DONE;
            // Enable monitors if requested via CFG
            mmwDemo_MonitorConfig();
            // Enable Monitors configured (They have to be enabled only during frame idle time)
            MMWave_enableMonitors(gMmwMssMCB.ctrlHandle);
            SemaphoreP_pend(&gMmwMssMCB.rfmonSemHandle, SystemP_WAIT_FOREVER);
            rfMonSemFactCalFlag = 0;
    
            /*Storing Loopback & Ball Break Monitors Results during Factory Calibration
            * These two monitor results are saved during Factory Calibration, to calculate
            * Tx Loopback Rx Gain Mismatch after zeroing time-0 mismatch 
            * Tx Loopback Rx Phase Mismatch after zeroing time-0 mismatch
            * Tx Gain Mismatch after zeroing time-0 mismatch 
            * Tx Phase Mismatch after zeroing time-0 mismatch
            * Change in return loss from factory (Ball Break Monitor)
            *
            * This is a one time activity and user can store these results in flash memory for use in subsequent runs
            */
           
            rfMonResFactCal=gMmwMssMCB.rfMonRes;
        }     
#endif
    /* Save calibration data in flash */
    if(gMmwMssMCB.factoryCalCfg.saveEnable != 0)
    {
        gFactoryCalibDataStorage.magic = MMWDEMO_CALIB_STORE_MAGIC;
        retVal = rl_fecssRfRxTxCalDataGet(M_DFP_DEVICE_INDEX_0, &gFactoryCalibDataStorage.calibData);
        if(retVal != M_DFP_RET_CODE_OK)
        {
            /* Error: Calibration data restore failed */
            CLI_write("Error: MMW demo failed rl_fecssRfFactoryCalDataGet with Error[%d]\n", retVal);
            retVal = SystemP_FAILURE;
        }

            /* Save data in flash */
            retVal = MmwDemo_calibSave(&gFactoryCalibDataStorage);
            if(retVal < 0)
            {
                CLI_write("Error: MMW demo failed Calibration Save with Error[%d]\n", retVal);
                MmwDemo_debugAssert (0);
            }
    }

    /* Configuring command for Run time CLPC calibration (Required if CLPC calib is enabled) */
    gMmwMssMCB.fecTxclpcCalCmd.c_CalMode = 0x0u; /* No Override */
    gMmwMssMCB.fecTxclpcCalCmd.c_CalTxBackOffSel[0] = factoryCalCfg.fecRFFactoryCalCmd.c_CalTxBackOffSel[0];
    gMmwMssMCB.fecTxclpcCalCmd.c_CalTxBackOffSel[1] = factoryCalCfg.fecRFFactoryCalCmd.c_CalTxBackOffSel[1];
    gMmwMssMCB.fecTxclpcCalCmd.h_CalRfFreq = factoryCalCfg.fecRFFactoryCalCmd.h_CalRfFreq;
    gMmwMssMCB.fecTxclpcCalCmd.xh_CalRfSlope = factoryCalCfg.fecRFFactoryCalCmd.xh_CalRfSlope;
    gMmwMssMCB.fecTxclpcCalCmd.c_TxPwrCalTxEnaMask[0] = factoryCalCfg.fecRFFactoryCalCmd.c_TxPwrCalTxEnaMask[0];
    gMmwMssMCB.fecTxclpcCalCmd.c_TxPwrCalTxEnaMask[1] = factoryCalCfg.fecRFFactoryCalCmd.c_TxPwrCalTxEnaMask[1];

    return retVal;
}