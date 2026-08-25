"""Prebuilt firmware bundled with the package."""

from importlib import resources
from pathlib import Path

BUNDLED_APPIMAGE_NAME = "mmwave_demo.Release.appimage"


def get_bundled_appimage() -> Path:
    """Path to the bundled material-classification firmware appimage.

    This is the Release build of the in-repo firmware
    (``hardware/firmware/IWRL6432BOOST_firmware/material_classification``).
    """
    ref = resources.files(__package__) / BUNDLED_APPIMAGE_NAME
    with resources.as_file(ref) as path:
        return Path(path)
