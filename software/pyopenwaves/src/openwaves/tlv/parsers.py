"""Payload parsers for the standard mmWave demo TLV types.

Every parser has the signature ``parser(payload: bytes, frame: FrameData)``
and mutates ``frame`` in place. Parsers never raise on malformed payloads —
they append a message to ``frame.errors`` instead, so one bad TLV cannot
kill a streaming loop.
"""

from __future__ import annotations

import struct

import numpy as np

from ..frames import ExtStats, FrameData, Track
from . import defines

_POINT_COLUMNS = 7  # x, y, z, doppler, snr, noise, track_index


def _ensure_points(frame: FrameData, n: int) -> np.ndarray:
    if frame.points is None or len(frame.points) < n:
        pts = np.zeros((n, _POINT_COLUMNS), np.float64)
        pts[:, 6] = defines.TRACK_INDEX_NOISE  # 255 = not associated
        if frame.points is not None and len(frame.points):
            pts[: len(frame.points)] = frame.points
        frame.points = pts
    return frame.points


def parse_detected_points(payload: bytes, frame: FrameData) -> None:
    """TLV 1: uncompressed cartesian points (4 floats: x, y, z, doppler)."""
    n = len(payload) // 16
    if n == 0:
        return
    data = np.frombuffer(payload[: n * 16], dtype="<f4").reshape(n, 4)
    points = _ensure_points(frame, n)
    points[:n, 0:4] = data
    frame.num_points = max(frame.num_points, n)


def parse_side_info(payload: bytes, frame: FrameData) -> None:
    """TLV 7: per-point SNR and noise as uint16 in 0.1 dB steps."""
    n = len(payload) // 4
    if n == 0:
        return
    data = np.frombuffer(payload[: n * 4], dtype="<u2").reshape(n, 2)
    points = _ensure_points(frame, n)
    points[:n, 4:6] = data * 0.1


def parse_detected_points_ext(payload: bytes, frame: FrameData) -> None:
    """TLV 301: compressed points — a unit struct then int16/uint8 points.

    Unit struct: 4 floats (xyz, doppler, snr, noise decompression units) +
    2 int16 padding. Each point: 4 int16 (x, y, z, doppler) + 2 uint8
    (snr, noise).
    """
    unit_size = struct.calcsize("<4f2h")
    point_size = struct.calcsize("<4h2B")
    if len(payload) < unit_size:
        frame.errors.append("TLV 301 shorter than its unit header")
        return
    xyz_unit, doppler_unit, snr_unit, noise_unit = struct.unpack_from("<4f", payload)
    n = (len(payload) - unit_size) // point_size
    points = _ensure_points(frame, n)
    offset = unit_size
    for i in range(n):
        x, y, z, doppler, snr, noise = struct.unpack_from("<4h2B", payload, offset)
        offset += point_size
        points[i, 0] = x * xyz_unit
        points[i, 1] = y * xyz_unit
        points[i, 2] = z * xyz_unit
        points[i, 3] = doppler * doppler_unit
        points[i, 4] = snr * snr_unit
        points[i, 5] = noise * noise_unit
    frame.num_points = max(frame.num_points, n)


def parse_range_profile(payload: bytes, frame: FrameData) -> None:
    """TLV 2: one uint32 per range bin."""
    frame.range_profile = np.frombuffer(payload[: len(payload) // 4 * 4], dtype="<u4").copy()


def parse_range_profile_major(payload: bytes, frame: FrameData) -> None:
    frame.range_profile_major = np.frombuffer(
        payload[: len(payload) // 4 * 4], dtype="<u4"
    ).copy()


def parse_range_profile_minor(payload: bytes, frame: FrameData) -> None:
    frame.range_profile_minor = np.frombuffer(
        payload[: len(payload) // 4 * 4], dtype="<u4"
    ).copy()


def parse_capon_heatmap(payload: bytes, frame: FrameData) -> None:
    """TLV 601 (OpenWaves custom): capon 3D beamforming spectrum, float32.

    With the standard 5120 floats the array is reshaped to
    ``defines.CAPON_HEATMAP_SHAPE`` = (10, 32, 16) — (depth, height, width);
    any other size is kept flat.
    """
    flat = np.frombuffer(payload[: len(payload) // 4 * 4], dtype="<f4").copy()
    expected = int(np.prod(defines.CAPON_HEATMAP_SHAPE))
    if flat.size == expected:
        frame.capon_heatmap = flat.reshape(defines.CAPON_HEATMAP_SHAPE)
    else:
        frame.capon_heatmap = flat
        frame.errors.append(
            f"capon heatmap has {flat.size} floats (expected {expected}); kept flat"
        )


def parse_target_list(payload: bytes, frame: FrameData) -> None:
    """TLV 308 / 1010: 3D tracker target list (uint32 id + 27 floats)."""
    target_struct = "<I27f"
    size = struct.calcsize(target_struct)
    n = len(payload) // size
    tracks: list[Track] = []
    for i in range(n):
        vals = struct.unpack_from(target_struct, payload, i * size)
        tracks.append(
            Track(
                track_id=vals[0],
                position=np.array(vals[1:4]),
                velocity=np.array(vals[4:7]),
                acceleration=np.array(vals[7:10]),
                # vals[10:26] is the 4x4 error covariance (discarded)
                g=vals[26],
                confidence=vals[27],
            )
        )
    frame.tracks = tracks


def parse_target_index(payload: bytes, frame: FrameData) -> None:
    """TLV 309 / 1011: one uint8 track index per point of the *previous* frame."""
    indexes = np.frombuffer(payload, dtype=np.uint8).astype(np.float64)
    frame.track_indexes = indexes
    if frame.points is not None:
        n = min(len(indexes), len(frame.points))
        frame.points[:n, 6] = indexes[:n]


def parse_micro_doppler_raw(payload: bytes, frame: FrameData) -> None:
    """TLV 310: float32 micro-Doppler spectrum, (num_targets, bins) flat."""
    frame.micro_doppler = np.frombuffer(
        payload[: len(payload) // 4 * 4], dtype="<f4"
    ).copy()
    _reshape_micro_doppler(frame)


def parse_micro_doppler_features(payload: bytes, frame: FrameData) -> None:
    """TLV 311: 6 floats per target (fLow, fUp, bwPwr, meanFreq, medFreq, sEntropy)."""
    size = struct.calcsize("<6f")
    n = len(payload) // size
    features = []
    for i in range(n):
        f_low, f_up, bw_pwr, mean_freq, med_freq, s_entropy = struct.unpack_from(
            "<6f", payload, i * size
        )
        features.append(
            {
                "fLow": f_low,
                "fUp": f_up,
                "bwPwr": bw_pwr,
                "meanFreq": mean_freq,
                "medFreq": med_freq,
                "sEntropy": s_entropy,
            }
        )
    frame.micro_doppler_features = features
    _reshape_micro_doppler(frame)


def _reshape_micro_doppler(frame: FrameData) -> None:
    md = frame.micro_doppler
    feats = frame.micro_doppler_features
    if md is None or md.ndim != 1 or not feats:
        return
    n_targets = len(feats)
    if n_targets > 0 and md.size % n_targets == 0:
        frame.micro_doppler = md.reshape(n_targets, md.size // n_targets)


def parse_enhanced_presence(payload: bytes, frame: FrameData) -> None:
    """TLV 315: first byte = zone count, then 2 bits of occupancy per zone."""
    if not payload:
        return
    num_zones = payload[0]
    zones: list[int] = []
    data = payload[1:]
    for zone in range(num_zones):
        idx = zone // 4
        if idx >= len(data):
            frame.errors.append("TLV 315 truncated")
            break
        zones.append((data[idx] >> ((zone * 2) % 8)) & 3)
    frame.presence = zones


def parse_classifier_info(payload: bytes, frame: FrameData) -> None:
    """TLV 317: per-target class probabilities as int8 / 128."""
    k = defines.NUM_CLASSES_IN_CLASSIFIER
    n = len(payload) // k
    if n == 0:
        return
    raw = np.frombuffer(payload[: n * k], dtype=np.uint8).reshape(n, k)
    frame.classifier_probabilities = raw.astype(np.float64) / 128.0


def parse_ext_stats(payload: bytes, frame: FrameData) -> None:
    """TLV 306: 2 uint32 timings + 4 uint16 powers + 4 uint16 temperatures."""
    fmt = "<2I8H"
    if len(payload) < struct.calcsize(fmt):
        frame.errors.append("TLV 306 too short")
        return
    vals = struct.unpack_from(fmt, payload)
    frame.stats = ExtStats(
        inter_frame_proc_time_us=vals[0],
        transmit_out_time_us=vals[1],
        power_1v8_mw=vals[2],
        power_3v3_mw=vals[3],
        power_1v2_mw=vals[4],
        power_1v2_rf_mw=vals[5],
        temp_rx_c=vals[6],
        temp_tx_c=vals[7],
        temp_pm_c=vals[8],
        temp_dig_c=vals[9],
    )
