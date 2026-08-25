"""Frame *encoder* — builds byte-exact frames for tests and simulation.

The encoder is the mirror image of the parser: it produces the same wire
format the firmware emits (magic word, 40-byte header, TLV items, zero
padding to a 32-byte multiple), which gives the test suite bit-level
round-trip coverage without hardware.
"""

from __future__ import annotations

import struct

import numpy as np

from . import defines


def encode_frame(
    tlvs: list[tuple[int, bytes]],
    *,
    frame_number: int = 0,
    num_detected_obj: int = 0,
    version: int = 0x05050300,
    platform: int = 0x6432,
    time_cpu_cycles: int = 0,
    subframe_number: int = 0,
) -> bytes:
    """Build one complete frame from ``(tlv_type, payload)`` pairs."""
    body = b"".join(
        struct.pack(defines.TLV_HEADER_STRUCT, tlv_type, len(payload)) + payload
        for tlv_type, payload in tlvs
    )
    unpadded = defines.FRAME_HEADER_SIZE + len(body)
    total_packet_len = -(-unpadded // defines.FRAME_PADDING) * defines.FRAME_PADDING
    header = struct.pack(
        defines.FRAME_HEADER_STRUCT,
        int.from_bytes(defines.MAGIC_WORD, "little"),
        version,
        total_packet_len,
        platform,
        frame_number,
        time_cpu_cycles,
        num_detected_obj,
        len(tlvs),
        subframe_number,
    )
    return header + body + b"\x00" * (total_packet_len - unpadded)


def encode_detected_points(points_xyzd: np.ndarray) -> tuple[int, bytes]:
    """TLV 1 payload from an (N, 4) float array of x, y, z, doppler."""
    return (
        defines.DETECTED_POINTS,
        np.asarray(points_xyzd, dtype="<f4").reshape(-1, 4).tobytes(),
    )


def encode_side_info(snr_db: np.ndarray, noise_db: np.ndarray) -> tuple[int, bytes]:
    """TLV 7 payload from per-point SNR / noise in dB (0.1 dB wire steps)."""
    data = np.stack(
        [np.round(np.asarray(snr_db) * 10), np.round(np.asarray(noise_db) * 10)],
        axis=1,
    ).astype("<u2")
    return defines.DETECTED_POINTS_SIDE_INFO, data.tobytes()


def encode_capon_heatmap(heatmap: np.ndarray) -> tuple[int, bytes]:
    """TLV 601 payload from a heatmap array (any shape, float32 on the wire)."""
    return (
        defines.CAPON_SPECTRUM_3D_HEATMAP,
        np.asarray(heatmap, dtype="<f4").ravel().tobytes(),
    )


def encode_ext_stats(
    inter_frame_proc_time_us: int = 0,
    transmit_out_time_us: int = 0,
    power_mw: tuple[int, int, int, int] = (0, 0, 0, 0),
    temp_c: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> tuple[int, bytes]:
    """TLV 306 payload."""
    return (
        defines.EXT_STATS,
        struct.pack("<2I8H", inter_frame_proc_time_us, transmit_out_time_us, *power_mw, *temp_c),
    )


def encode_target_list(tracks: list[dict]) -> tuple[int, bytes]:
    """TLV 308 payload from dicts with track_id/position/velocity/acceleration/g/confidence."""
    payload = b""
    for t in tracks:
        ec = [0.0] * 16
        payload += struct.pack(
            "<I27f",
            t["track_id"],
            *t["position"],
            *t["velocity"],
            *t["acceleration"],
            *ec,
            t.get("g", 0.0),
            t.get("confidence", 0.0),
        )
    return defines.EXT_TARGET_LIST, payload
