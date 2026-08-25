from importlib import resources
from pathlib import Path

from .cfgfile import parse_cfg, parse_cfg_text
from .model import (
    COMMAND_CLASSES,
    AntGeometryCfg,
    AoaFovCfg,
    BaudRate,
    CfarCfg,
    ChannelCfg,
    ChirpComnCfg,
    ChirpTimingCfg,
    ClutterRemoval,
    Command,
    FactoryCalibCfg,
    FrameCfg,
    GuiMonitor,
    LowPowerCfg,
    RadarConfig,
    RangeSelCfg,
    RawCommand,
    SensorPosition,
    SensorStart,
    SensorStop,
    SigProcChainCfg,
)


def get_profile_cfg(name: str) -> Path:
    """Path to a packaged configuration profile.

    Available profiles: ``mpd_tracking_midbw`` (TI Motion-and-Presence
    firmware, point cloud + tracking) and ``material_classification_default``
    (in-repo firmware, capon 3D heatmap).
    """
    ref = resources.files(__package__) / "profiles" / f"{name}.cfg"
    with resources.as_file(ref) as path:
        return Path(path)


__all__ = [
    "parse_cfg",
    "parse_cfg_text",
    "get_profile_cfg",
    "COMMAND_CLASSES",
    "AntGeometryCfg",
    "AoaFovCfg",
    "BaudRate",
    "CfarCfg",
    "ChannelCfg",
    "ChirpComnCfg",
    "ChirpTimingCfg",
    "ClutterRemoval",
    "Command",
    "FactoryCalibCfg",
    "FrameCfg",
    "GuiMonitor",
    "LowPowerCfg",
    "RadarConfig",
    "RangeSelCfg",
    "RawCommand",
    "SensorPosition",
    "SensorStart",
    "SensorStop",
    "SigProcChainCfg",
]
