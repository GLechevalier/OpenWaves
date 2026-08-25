"""Firmware CLI command sets ("profiles"), as data.

Two different firmware images are relevant to OpenWaves and they do NOT
accept the same CLI commands:

* ``MATERIAL_CLASSIFICATION_PROFILE`` — the firmware in this repository
  (``hardware/firmware/IWRL6432BOOST_firmware/material_classification``).
  Command table extracted from its ``mmw_cli.c``. Streams the custom capon
  3D heatmap TLV (type 601) on the CLI UART (single-port layout).
* ``MPD_PROFILE`` — TI's stock Motion and Presence Detection demo (what the
  ``.cfg`` files in ``software/fall_detection_example/cfg`` target). Adds the
  tracker/classifier commands and streams TLVs on the auxiliary data port.

Profiles are used for *validation with a warning only* — an unknown command
is still sent, so new firmware commands never require a package update.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandSpec:
    """One CLI command: its name and the argument signature it documents."""

    name: str
    help: str = ""


@dataclass(frozen=True)
class FirmwareProfile:
    """A named set of CLI commands one firmware image understands."""

    name: str
    commands: dict[str, CommandSpec] = field(default_factory=dict)
    #: True if the TLV stream shares the CLI UART (single COM port layout)
    single_port: bool = False

    def knows(self, command_name: str) -> bool:
        return command_name in self.commands

    def warn_if_unknown(self, command_name: str) -> None:
        if not self.knows(command_name):
            log.warning(
                "Command %r is not in the %s firmware command table — "
                "sending anyway (the firmware will answer 'not recognized' "
                "if it really doesn't support it).",
                command_name,
                self.name,
            )


def _profile(name: str, specs: list[tuple[str, str]], *, single_port: bool) -> FirmwareProfile:
    return FirmwareProfile(
        name=name,
        commands={n: CommandSpec(n, h) for n, h in specs},
        single_port=single_port,
    )


# Extracted from mmw_cli.c of the in-repo material_classification firmware.
_MATERIAL_CLASSIFICATION_COMMANDS: list[tuple[str, str]] = [
    ("sensorStop", "<FrameStopMode>"),
    ("channelCfg", "<RxChCtrlBitMask> <TxChCtrlBitMask> <MiscCtrl>"),
    (
        "chirpComnCfg",
        "<DigOutputSampRate_Decim> <DigOutputBitsSel> <DfeFirSel> <NumOfAdcSamples> "
        "<ChirpTxMimoPatSel> <ChirpRampEndTime> <ChirpRxHpfSel>",
    ),
    (
        "chirpTimingCfg",
        "<ChirpIdleTime> <ChirpAdcSkipSamples> <ChirpTxStartTime> <ChirpRfFreqSlope> "
        "<ChirpRfFreqStart>",
    ),
    (
        "frameCfg",
        "<NumOfChirpsInBurst> <NumOfChirpsAccum> <BurstPeriodicity> <NumOfBurstsInFrame> "
        "<FramePeriodicity> <NumOfFrames>",
    ),
    (
        "guiMonitor",
        "<pointCloud> <rangeProfile> <noiseProfile> <rangeAzimuthHeatMap> "
        "<rangeDopplerHeatMap> <statsInfo> <presenceInfo> <adcSamples> <trackerInfo> "
        "<microDopplerInfo> <classifierInfo>",
    ),
    (
        "sigProcChainCfg",
        "<azimuthFftSize> <elevationFftSize> <motDetMode> <coherentDoppler> "
        "<numFrmPerMinorMotProc> <numMinorMotionChirpsPerFrame> "
        "<forceMinorMotionVelocityToZero> <minorMotionVelocityInclusionThr>",
    ),
    (
        "cfarCfg",
        "<averageMode> <winLen> <guardLen> <noiseDiv> <cyclicMode> <thresholdScale> "
        "<peakGroupingEn>",
    ),
    (
        "cfarScndPassCfg",
        "<enabled> <averageMode> <winLen> <guardLen> <noiseDiv> <cyclicMode> "
        "<thresholdScale> <peakGroupingEn>",
    ),
    ("aoaFovCfg", "<minAzimuthDeg> <maxAzimuthDeg> <minElevationDeg> <maxElevationDeg>"),
    ("rangeSelCfg", "<minMeters> <maxMeters>"),
    ("clutterRemoval", "<0-disable, 1-enable>"),
    (
        "compRangeBiasAndRxChanPhase",
        "<rangeBias> <Re00> <Im00> <Re01> <Im01> <Re02> <Im02> <Re03> <Im03> <Re04> "
        "<Im04> <Re05> <Im05>",
    ),
    ("adcDataSource", "<0-DFP, 1-File> <fileName>"),
    (
        "adcLogging",
        "<0-disable, 1-enableDCA, 2-enableSPI> <sideBandEnable> <swizzlingMode> "
        "<scramblerMode> <laneRate>",
    ),
    ("sensorPosition", "<xOffset> <yOffset> <zOffset> <azimuthTilt> <elevationTilt>"),
    ("sensorStart", "<FrameTrigMode> <LoopBackEn> <FrameLivMonEn> <FrameTrigTimerVal>"),
    ("lowPowerCfg", "<LowPowerModeEnable>"),
    ("enableRFmons", "<ListofMonsToEnable>"),
    ("monPllCtrlVolt", "<ListofVoltagemonitorsToEnable>"),
    (
        "monTxRxLbCfg",
        "<TX inst> <Mon Enable Ctrl> <TxRx Code Sel> <Rx Gain code> <Tx Bias Code> "
        "<RF FreqGHz> <RF Freq SlopeMhz/us>",
    ),
    (
        "monTxnPowCfg",
        "<TX inst> <Tx Bias Sel> <Tx Bias Code> <RF FreqGHz> <RF Freq SlopeMhz/us> "
        "<TX Backoff>",
    ),
    (
        "monTxnBBPowCfg",
        "<TX inst> <Tx Bias Sel> <Tx Bias Code> <RF FreqGHz> <RF Freq SlopeMhz/us> "
        "<TX Backoff>",
    ),
    (
        "monTxnDcSigCfg",
        "<TX inst> <Tx Bias Sel> <Tx Bias Code> <RF FreqGHz> <RF Freq SlopeMhz/us> "
        "<TX Backoff>",
    ),
    ("monRxHpfDcSigCfg", "<RF StartFreqGHz> <Mon Enable Ctrl> <RX HPF Corner Freq Sel>"),
    ("monPmClkDcCfg", "<RF StartFreqGHz>"),
    ("factoryCalibCfg", "<save enable> <restore enable> <rxGain> <backoff0> <Flash offset>"),
    ("baudRate", "<baudRate>"),
    (
        "antGeometryCfg",
        "<row0> <col0> <row1> <col1> <row2> <col2> <row3> <col3> <row4> <col4> "
        "<row5> <col5> <antDistX (mm)> <antDistY (mm)>",
    ),
    ("measureRangeBiasAndRxChanPhase", "<enabled> <targetDistance> <searchWin>"),
    ("sensorWarmRst", "<Reserved>"),
    ("compressionCfg", "<enabled> <compresssionRatio>"),
    ("help", ""),
]

# TI's Motion and Presence Detection demo additions (from its documented CLI
# and the .cfg files under software/fall_detection_example/cfg).
_MPD_EXTRA_COMMANDS: list[tuple[str, str]] = [
    ("boundaryBox", "<xMin> <xMax> <yMin> <yMax> <zMin> <zMax>"),
    ("staticBoundaryBox", "<xMin> <xMax> <yMin> <yMax> <zMin> <zMax>"),
    ("presenceBoundaryBox", "<xMin> <xMax> <yMin> <yMax> <zMin> <zMax>"),
    ("gatingParam", "<gain> <widthLimit> <depthLimit> <heightLimit> <velocityLimit>"),
    ("stateParam", "<det2act> <det2free> <act2free> <stat2free> <exit2free> <sleep2free>"),
    (
        "allocationParam",
        "<snrThre> <snrThreObscured> <velocityThre> <pointsThre> <maxDistanceThre> "
        "<maxVelThre>",
    ),
    ("maxAcceleration", "<maxAccelX> <maxAccelY> <maxAccelZ>"),
    (
        "trackingCfg",
        "<enable> <dimensionality> <maxNumPoints> <maxNumTracks> <maxRadialVelocity> "
        "<radialVelocityResolution> <deltaT>",
    ),
    (
        "microDopplerCfg",
        "<enabled> <genAllTracks> <magnitudeSquared> <circShiftCentroid> <normalize> "
        "<specSmoothingFactor> <interceptThrLowFreq> <interceptThrHighFreq> <specWinLen>",
    ),
    ("classifierCfg", "<enabled> <minNumPntsPerTrack> <missTotFrmThre>"),
    ("mpdBoundaryBox", "<zoneIdx> <xMin> <xMax> <yMin> <yMax> <zMin> <zMax>"),
    ("clusterCfg", "<enabled> <maxDistance> <minPoints>"),
    ("minorStateCfg", "see TI MPD demo docs"),
    ("majorStateCfg", "see TI MPD demo docs"),
    ("flushCfg", ""),
]

MATERIAL_CLASSIFICATION_PROFILE = _profile(
    "material_classification", _MATERIAL_CLASSIFICATION_COMMANDS, single_port=True
)

MPD_PROFILE = _profile(
    "motion_and_presence_detection",
    _MATERIAL_CLASSIFICATION_COMMANDS + _MPD_EXTRA_COMMANDS,
    single_port=False,
)

PROFILES = {
    p.name: p
    for p in (MATERIAL_CLASSIFICATION_PROFILE, MPD_PROFILE)
}
