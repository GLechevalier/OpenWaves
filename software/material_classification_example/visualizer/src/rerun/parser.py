"""Compatibility shim — the RadarWall BLE client now lives in the
``openwaves`` package (``pip install -e software/openwaves[ble]``).

Import from :mod:`openwaves.ble` in new code.
"""

from openwaves.ble import (  # noqa: F401
    COMMAND_CHARACTERISTIC_UUID,
    DATA_CHARACTERISTIC_UUID,
    DEVICE_NAME,
    HEATMAP_FLOAT_COUNT,
    HEATMAP_SHAPE,
    SERVICE_UUID,
    ChunkHeader,
    FrameHeader,
    FrameState,
    RadarWallBLEClient,
)
from openwaves.ble.radarwall import (  # noqa: F401
    CHUNK_HEADER_SIZE,
    FRAME_HEADER_SIZE,
    MAX_CHUNK_PAYLOAD_SIZE,
    MAX_RETRIES,
    PACKET_TIMEOUT_MS,
    TRANSMISSION_TIMEOUT_MS,
)
