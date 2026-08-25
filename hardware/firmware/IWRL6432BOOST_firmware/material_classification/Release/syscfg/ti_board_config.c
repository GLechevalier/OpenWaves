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
#include "ti_board_config.h"

/*
 * Auto generated file
 */


#include <board/ina.h>
#include <math.h>

void SensorConfig(I2C_Handle i2cHandle)
{

    // Configure the INA228
    SensorConfig228(i2cHandle, INA_CONFIG0_TARGET_ADDRESS, INA_CONFIG0_REG0_VALUE, INA_CONFIG0_REG1_VALUE, INA_CONFIG0_SHUNT_TEMP_REG_VALUE, INA_CONFIG0_CALIB_REG_VALUE);


    // Configure the INA228
    SensorConfig228(i2cHandle, INA_CONFIG1_TARGET_ADDRESS, INA_CONFIG1_REG0_VALUE, INA_CONFIG1_REG1_VALUE, INA_CONFIG1_SHUNT_TEMP_REG_VALUE, INA_CONFIG1_CALIB_REG_VALUE);


    // Configure the INA228
    SensorConfig228(i2cHandle, INA_CONFIG2_TARGET_ADDRESS, INA_CONFIG2_REG0_VALUE, INA_CONFIG2_REG1_VALUE, INA_CONFIG2_SHUNT_TEMP_REG_VALUE, INA_CONFIG2_CALIB_REG_VALUE);

}

void mmwDemo_PowerMeasurement(I2C_Handle i2cHandle, uint16_t *ptrPwrMeasured)
{
    float current;
    current = currentRead228(i2cHandle,64,INA_CONFIG0_CURRENT_LSB);
    ptrPwrMeasured[0] =  (current == (float)0xFFFFFFFF) ? 0xFFFF : (uint16_t) round(current * 18000.0);  //Rail 1.8V, current reading in mA, power measurement in 100 uW

    current = currentRead228(i2cHandle,65,INA_CONFIG1_CURRENT_LSB);
    ptrPwrMeasured[2] = (current== (float)0xFFFFFFFF) ? 0xFFFF : (uint16_t) round(current * 12000.0);  //Rail 1.2V, current reading in mA, power measurement in 100uW

    current = currentRead228(i2cHandle,68,INA_CONFIG2_CURRENT_LSB);
    ptrPwrMeasured[3] = (current == (float)0xFFFFFFFF) ? 0xFFFF : (uint16_t) round(current * 12000.0);  //Rail RF 1.2V, current reading in mA, power measurement in 100 uW

}



void Board_init(void)
{
}

void Board_deinit(void)
{
}
