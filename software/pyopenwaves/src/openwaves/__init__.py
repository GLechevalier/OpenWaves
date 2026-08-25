"""openwaves — Python toolkit for the TI IWRL6432BOOST mmWave radar.

Flash firmware, send configurations, stream and parse TLV frames — with no
TI software installed. See docs/ in the OpenWaves repository.

Quick start::

    from openwaves import Radar

    with Radar() as radar:
        radar.configure("cfg/Tracking_MidBw.cfg")
        radar.start()
        for frame in radar.frames(count=10):
            print(frame.frame_number, frame.num_points)
"""

from ._version import __version__
from .exceptions import (
    CliCommandError,
    CliTimeoutError,
    FlashError,
    FrameSyncError,
    OpenWavesError,
    PortNotFoundError,
)
from .frames import ExtStats, FrameData, Track
from .radar import Radar

__all__ = [
    "__version__",
    "Radar",
    "FrameData",
    "Track",
    "ExtStats",
    "OpenWavesError",
    "PortNotFoundError",
    "CliTimeoutError",
    "CliCommandError",
    "FrameSyncError",
    "FlashError",
    "find_radar_ports",
    "find_all_radars",
    "flash_firmware",
    "get_bundled_appimage",
]


def __getattr__(name: str):
    # Lazy imports keep 'import openwaves' fast and dependency-light.
    if name in ("find_radar_ports", "find_all_radars"):
        from . import transport

        return getattr(transport, name)
    if name == "flash_firmware":
        from .flash import flash_firmware

        return flash_firmware
    if name == "get_bundled_appimage":
        from .firmware import get_bundled_appimage

        return get_bundled_appimage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
