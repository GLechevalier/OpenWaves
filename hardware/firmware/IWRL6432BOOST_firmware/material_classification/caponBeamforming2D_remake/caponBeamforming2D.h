/**
 *   @file  caponbeamforming2D.h
 *
 *   @brief
 *      Implements 2D Capon Beamforming functionality.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2025 Gauthier Lechevalier
 *
 */

/**************************************************************************
 *************************** Include Files ********************************
 **************************************************************************/

#ifndef CAPONBEAMFORMING2D_H
#define CAPONBEAMFORMING2D_H

/* Standard Include Files. */
#include <stdint.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <math.h>

/* mmWave SDK Driver/Common Include Files */
#include <drivers/hwa.h>

/* DPIF Components Include Files */
#include <datapath/dpedma/v0/dpedmahwa.h>
#include <datapath/dpedma/v0/dpedma.h>

/* mmWave SDK Data Path Include Files */
#include <datapath/dpif/dp_error.h>

#ifdef __cplusplus
extern "C" {
#endif

/** @addtogroup DPU_CAPONBEAMFORMING2D_ERROR_CODE
 *  Base error code for the caponbeamforming2D DPU is defined in the
 *  \include ti/datapath/dpif/dp_error.h
 @{ */

/**
 * @brief   Error Code: Invalid argument
 */
#define CAPONBEAMFORMING2DHWA_EINVAL                  (DP_ERRNO_CAPONBEAMFORMING2D_BASE-1)

/**
 * @brief   Error Code: Out of memory
 */
#define CAPONBEAMFORMING2DHWA_ENOMEM                  (DP_ERRNO_CAPONBEAMFORMING2D_BASE-2)

/**
 * @brief   Error Code: Out of HWA resources
 */
#define CAPONBEAMFORMING2DHWA_EHWARES                 (DP_ERRNO_CAPONBEAMFORMING2D_BASE-3)

/**
 * @brief   Error Code: Semaphore creation failed
 */
#define CAPONBEAMFORMING2DHWA_ESEMA                   (DP_ERRNO_CAPONBEAMFORMING2D_BASE-4)

/**
 * @brief   Error Code: Configure parameters exceed HWA memory bank size
 */
#define CAPONBEAMFORMING2DHWA_EEXCEEDHWAMEM           (DP_ERRNO_CAPONBEAMFORMING2D_BASE-5)

/**
 * @brief   Error Code: HWA Correlation Matrix and Capon Spectrum paramset indices do not conflict
 */
#define CAPONBEAMFORMING2DHWA_HWAPARAMSETSCONFLICT    (DP_ERRNO_CAPONBEAMFORMING2D_BASE-5)

/**
 * @brief   Number of HWA memory banks needed
 */
#define CAPONBEAMFORMING2DHWA_NUM_HWA_MEMBANKS    4
#define MAX_NUM_ANTENNAS                        6
#define MAX_ANGLES_AZIMUTH                      64
#define MAX_ANGLES_ELEVATION                    32


/*!
 *  @brief   Handle for Capon Beamforming 2D DPU.
 */
typedef void*  CaponBeamforming2DHWA_Handle;

/**
 * @brief
 *  Capon Beamforming 2D DPU initial configuration parameters
 *
 * @details
 *  The structure is used to hold the DPU initial configurations.
 *
 *  \ingroup DPU_CAPONBEAMFORMING2D_EXTERNAL_DATA_STRUCTURE
 */
typedef struct CaponBeamforming2DHWA_InitCfg_t
{
    /*! @brief HWA Handle */
    HWA_Handle  hwaHandle;

} CaponBeamforming2DHWA_InitParams;

/**
 * @brief
 *  Capon Beamforming 2D DPU HWA configuration parameters
 *
 * @details
 *  The structure is used to hold the HWA configuration parameters
 *  for the Capon Beamforming 2D DPU
 *
 *  \ingroup DPU_CAPONBEAMFORMING2D_EXTERNAL_DATA_STRUCTURE
 */
typedef struct CaponBeamforming2DHWA_HwaCfg_t
{
    /*! @brief  PaRAM set start index for capon spectrum computation. */
    uint32_t    caponBeamforming2DParamSetStartIdx;
} CaponBeamforming2DHWA_HwaCfg;

/**
 * @brief
 *  Capon Beamforming 2D DPU EDMA configuration parameters
 *
 * @details
 *  The structure is used to hold the EDMA configuration parameters
 *  for the Capon Beamforming 2D DPU
 *
 *  \ingroup DPU_CAPONBEAMFORMING2D_EXTERNAL_DATA_STRUCTURE
 */
typedef struct CaponBeamforming2D_Edma_t
{
    /*! @brief  EDMA channel for the Capon Spectrum. */
    DPEDMA_ChanCfg  caponSpectrumChannel;
}CaponBeamforming2D_Edma;

/**
 * @brief
 *  Capon Beamforming 2D DPU EDMA configuration parameters
 *
 * @details
 *  The structure is used to hold the EDMA configuration parameters
 *  for the Capon Beamforming 2D DPU
 *
 *  \ingroup DPU_CAPONBEAMFORMING2D_EXTERNAL_DATA_STRUCTURE
 */
typedef struct CaponBeamforming2DHWA_EdmaCfg_t
{
    /*! @brief  EDMA driver handle. */
    EDMA_Handle edmaHandle;

    /*! @brief  EDMA configuration for Inputting data to the HWA */
    CaponBeamforming2D_Edma edmaIn;

    /*! @brief  EDMA configuration for Output data from the HWA */
    CaponBeamforming2D_Edma edmaOut;

    /*! @brief  EDMA configuration for hot signature. */
    CaponBeamforming2D_Edma edmaHotSig;
} CaponBeamforming2DHWA_EdmaCfg;

/**
 * @brief
 *  Capon Beamforming 2D HW configuration parameters
 *
 * @details
 *  The structure is used to hold the HW configuration parameters
 *  for Capon Beamforming 2D
 *
 *  \ingroup CAPON_BEAMFORMING2D_EXTERNAL_DATA_STRUCTURE
 */
typedef struct CaponBeamforming2DHWA_HW_Resources_t
{
    /*! @brief  EDMA configuration */
    CaponBeamforming2DHWA_EdmaCfg edmaCfg;

    /*! @brief  HWA configuration */
    CaponBeamforming2DHWA_HwaCfg  hwaCfg;

    /*! @brief  Input Data */
    int32_t *caponBeamforming2DInputData;

    /*! @brief  Capon Spectrum*/
    float   *caponSpectrum;

    /*! @brief  Maximum Value of the Capon Spectrum */
    float   maxCaponSpectrum;

    /*! @brief  Minimum Value of the Capon Spectrum */
    float   minCaponSpectrum;

    /*! @brief  The DMA Channel which will be used to trigger the HWA on DMA trigger */
    uint8_t   hwaDmaTriggerSourceCaponSpectrum;

    /*! @brief  Number of arrays to skip after storing the ouptut for the next elevation bin
    Ex: If numAnglesAzimuth = 32 and bCnt = 64, the DPU will skip 32*64*sizeof(float) bytes
    from the start address of the previous elevation bin and then store the current elevation bin  */
    uint8_t   bCnt;

    /*! @brief     EDMA interrupt object for the EDMA completion interrupt after
                   transfer of Capon Spectrum from the HWA to L3 */
    /* NOTE: Application needs to provide address of the EDMA interrupt object.
     * This needs to be done as there might be multiple subframes configured
     * and each subframe needs EDMA interrupt to be registered.
     */
    Edma_IntrObject intrObjCaponSpectrum;
} CaponBeamforming2DHWA_HW_Resources;

/**
 * @brief
 *  Capon Beamforming 2D DPU static configuration parameters
 *
 * @details
 *  The structure is used to hold the static configuration parameters
 *  for the Capon Beamforming 2D DPU. The following conditions must be satisfied:
 *
 *  \ingroup DPU_CAPONBEAMFORMING2D_EXTERNAL_DATA_STRUCTURE
 */
typedef struct CaponBeamforming2DHWA_StaticConfig_t
{
    /*! @brief  Number of virtual antennas */
    uint8_t     numVirtualAntennas;

    /*! @brief  Number of range bins */
    uint16_t    numSnapshots;

    /*! @brief  The number of angles to sample in azimuth in the Capon Spectrum  */
    uint8_t     numAnglesToSampleAzimuth;

    /*! @brief  The number of angles to sample in elevation in the Capon Spectrum  */
    uint8_t     numAnglesToSampleElevation;

    /*! @brief  Array of antenna coordinates read from the CLI stored in [col row] format
    NOTE: The CLI takes antenna geometry input in [row col] format. The format which this DPU expects is the opposite [col row]   */
    uint8_t     antennaCoordinates[12];

    /*! @brief  Boundary of the array of antenna coordinates in the x and z directions  */
    uint8_t     maxLimits[2];

} CaponBeamforming2DHWA_StaticConfig;

/**
 * @brief
 *  Capon Beamforming 2D DPU configuration parameters
 *
 * @details
 *  The structure is used to hold the configuration parameters
 *  for the Capon Beamforming 2D removal DPU
 *
 *  \ingroup DPU_CAPONBEAMFORMING2D_EXTERNAL_DATA_STRUCTURE
 */
typedef struct CaponBeamforming2DHWA_Config_t
{
    /*! @brief HW resources. */
    CaponBeamforming2DHWA_HW_Resources  hwRes;

    /*! @brief Static configuration. */
    CaponBeamforming2DHWA_StaticConfig  staticCfg;

} CaponBeamforming2DHWA_Config;


CaponBeamforming2DHWA_Handle CaponBeamforming2DHWA_init(CaponBeamforming2DHWA_InitParams *initCfg, int32_t* errCode);
int32_t caponBeamforming2D_process(CaponBeamforming2DHWA_Config *cfg, float *output);
//int32_t CaponBeamforming2DHWA_deinit(CaponBeamforming2DHWA_Handle handle, CaponBeamforming2DHWA_Config *cfg);
//int32_t CaponBeamforming2DHWA_config(CaponBeamforming2DHWA_Handle handle, CaponBeamforming2DHWA_Config *cfg);

#ifdef __cplusplus
}
#endif

#endif
