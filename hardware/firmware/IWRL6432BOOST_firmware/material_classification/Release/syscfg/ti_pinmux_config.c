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
#include <drivers/pinmux.h>

static Pinmux_PerCfg_t gPinMuxMainDomainCfg[] = {
            /* QSPI0 pin config */
    /* QSPI_DOUT -> PAD_AC (B11) */
    {
        PIN_PAD_AC,
        ( PIN_MODE(0) | PIN_PULL_DISABLE )
    },
    /* QSPI_DIN -> PAD_AD (B8) */
    {
        PIN_PAD_AD,
        ( PIN_MODE(0) | PIN_PULL_DISABLE )
    },
    /* QSPI_DIN0 -> PAD_AE (B10) */
    {
        PIN_PAD_AE,
        ( PIN_MODE(0) | PIN_PULL_DISABLE )
    },
    /* QSPI_DIN1 -> PAD_AF (B9) */
    {
        PIN_PAD_AF,
        ( PIN_MODE(0) | PIN_PULL_DISABLE )
    },
    /* QSPI_CLK -> PAD_AA (A11) */
    {
        PIN_PAD_AA,
        ( PIN_MODE(0) | PIN_PULL_DISABLE )
    },
    /* QSPI_CS -> PAD_AB (A10) */
    {
        PIN_PAD_AB,
        ( PIN_MODE(0) | PIN_PULL_DISABLE )
    },

            /* GPIO pin config */
    /* GPIO5 -> PAD_AV (J10) */
    {
        PIN_PAD_AV,
        ( PIN_MODE(0) | PIN_PULL_DISABLE )
    },

            /* I2C0 pin config */
    /* I2C_SCL -> PAD_AG (D10) */
    {
        PIN_PAD_AG,
        ( PIN_MODE(2) | PIN_PULL_DISABLE )
    },
    /* I2C_SDA -> PAD_AH (D11) */
    {
        PIN_PAD_AH,
        ( PIN_MODE(2) | PIN_PULL_DISABLE )
    },


            /* UARTB pin config */
    /* UARTB_RX -> PAD_AP (F11) */
    {
        PIN_PAD_AP,
        ( PIN_MODE(2) | PIN_PULL_DISABLE )
    },
    /* UARTB_TX -> PAD_AO (E10) */
    {
        PIN_PAD_AO,
        ( PIN_MODE(2) | PIN_PULL_DISABLE )
    },

    {PINMUX_END, PINMUX_END}
};


/*
 * Pinmux
 */
void Pinmux_init(void)
{
    Pinmux_config(gPinMuxMainDomainCfg, PINMUX_DOMAIN_ID_MAIN);
}

