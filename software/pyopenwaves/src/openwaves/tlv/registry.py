"""Extensible mapping of TLV type ids to parser functions."""

from __future__ import annotations

import math
import struct
import time
from typing import Callable

from ..frames import FrameData
from . import defines, parsers
from .header import FrameHeader

TlvParser = Callable[[bytes, FrameData], None]


class TlvRegistry:
    """Maps TLV type ids to parsers and parses whole frames.

    Registering your own TLV type::

        from openwaves.tlv import DEFAULT_REGISTRY

        def parse_my_tlv(payload: bytes, frame):
            frame.extras["my_value"] = int.from_bytes(payload[:4], "little")

        DEFAULT_REGISTRY.register(602, parse_my_tlv, name="myTlv")
    """

    def __init__(self):
        self._parsers: dict[int, TlvParser] = {}
        self._names: dict[int, str] = {}

    def register(self, tlv_type: int, parser: TlvParser, name: str | None = None) -> None:
        self._parsers[tlv_type] = parser
        if name:
            self._names[tlv_type] = name

    def unregister(self, tlv_type: int) -> None:
        self._parsers.pop(tlv_type, None)
        self._names.pop(tlv_type, None)

    def known_types(self) -> dict[int, str]:
        return {t: self._names.get(t, p.__name__) for t, p in self._parsers.items()}

    def parse_frame(self, frame_bytes: bytes, *, timestamp: float | None = None) -> FrameData:
        """Parse one complete frame (magic word included) into a FrameData.

        Malformed content is reported through ``FrameData.errors``; this
        method only raises for a frame too short to contain a header or with
        a bad magic word.
        """
        header = FrameHeader.from_bytes(frame_bytes)
        frame = FrameData(
            frame_number=header.frame_number,
            timestamp=timestamp if timestamp is not None else time.time(),
            num_detected_obj=header.num_detected_obj,
            subframe_number=header.subframe_number,
            version=header.version,
            platform=header.platform,
            time_cpu_cycles=header.time_cpu_cycles,
        )

        offset = defines.FRAME_HEADER_SIZE
        for i in range(header.num_tlvs):
            if offset + defines.TLV_HEADER_SIZE > len(frame_bytes):
                frame.errors.append(
                    f"frame truncated before TLV {i + 1}/{header.num_tlvs}"
                )
                break
            tlv_type, tlv_length = struct.unpack_from(
                defines.TLV_HEADER_STRUCT, frame_bytes, offset
            )
            offset += defines.TLV_HEADER_SIZE
            payload = frame_bytes[offset : offset + tlv_length]
            if len(payload) < tlv_length:
                frame.errors.append(
                    f"TLV type {tlv_type} truncated ({len(payload)}/{tlv_length} bytes)"
                )
                offset += tlv_length
                continue
            parser = self._parsers.get(tlv_type)
            if parser is None:
                frame.raw_tlvs[tlv_type] = payload
            else:
                try:
                    parser(payload, frame)
                except Exception as exc:  # a parser bug must not kill the stream
                    frame.errors.append(f"parser for TLV {tlv_type} failed: {exc!r}")
            offset += tlv_length

        # The device pads totalPacketLen to a multiple of 32; verify.
        padded = defines.FRAME_PADDING * math.ceil(offset / defines.FRAME_PADDING)
        if padded != header.total_packet_len:
            frame.errors.append(
                f"length check failed: read {offset} (padded {padded}) != "
                f"header totalPacketLen {header.total_packet_len}"
            )
        return frame


def default_registry() -> TlvRegistry:
    """A registry pre-loaded with every TLV type openwaves parses."""
    r = TlvRegistry()
    r.register(defines.DETECTED_POINTS, parsers.parse_detected_points, "detectedPoints")
    r.register(defines.DETECTED_POINTS_SIDE_INFO, parsers.parse_side_info, "sideInfo")
    r.register(defines.EXT_DETECTED_POINTS, parsers.parse_detected_points_ext, "extDetectedPoints")
    r.register(defines.RANGE_PROFILE, parsers.parse_range_profile, "rangeProfile")
    r.register(defines.EXT_RANGE_PROFILE_MAJOR, parsers.parse_range_profile_major, "rangeProfileMajor")
    r.register(defines.EXT_RANGE_PROFILE_MINOR, parsers.parse_range_profile_minor, "rangeProfileMinor")
    r.register(defines.CAPON_SPECTRUM_3D_HEATMAP, parsers.parse_capon_heatmap, "caponHeatmap3D")
    r.register(defines.EXT_TARGET_LIST, parsers.parse_target_list, "targetList")
    r.register(defines.TRACKERPROC_3D_TARGET_LIST, parsers.parse_target_list, "targetList3D")
    r.register(defines.EXT_TARGET_INDEX, parsers.parse_target_index, "targetIndex")
    r.register(defines.TRACKERPROC_TARGET_INDEX, parsers.parse_target_index, "targetIndex3D")
    r.register(defines.EXT_MICRO_DOPPLER_RAW_DATA, parsers.parse_micro_doppler_raw, "microDoppler")
    r.register(
        defines.EXT_MICRO_DOPPLER_FEATURES,
        parsers.parse_micro_doppler_features,
        "microDopplerFeatures",
    )
    r.register(
        defines.EXT_ENHANCED_PRESENCE_INDICATION,
        parsers.parse_enhanced_presence,
        "enhancedPresence",
    )
    r.register(defines.EXT_CLASSIFIER_INFO, parsers.parse_classifier_info, "classifierInfo")
    r.register(defines.EXT_STATS, parsers.parse_ext_stats, "extStats")
    return r


#: shared default registry — extend it to add custom TLV types globally
DEFAULT_REGISTRY = default_registry()
