"""Typed result objects produced by the TLV parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class ExtStats:
    """Timing / power / temperature statistics (TLV 306)."""

    inter_frame_proc_time_us: int
    transmit_out_time_us: int
    power_1v8_mw: int
    power_3v3_mw: int
    power_1v2_mw: int
    power_1v2_rf_mw: int
    temp_rx_c: int
    temp_tx_c: int
    temp_pm_c: int
    temp_dig_c: int


@dataclass
class Track:
    """One tracked target (TLV 308 / 1010)."""

    track_id: int
    position: np.ndarray  # (3,) x, y, z in m
    velocity: np.ndarray  # (3,) m/s
    acceleration: np.ndarray  # (3,) m/s^2
    g: float
    confidence: float


@dataclass
class FrameData:
    """Everything parsed out of one radar UART frame.

    ``points`` is an ``(N, 7)`` float array with columns
    ``x, y, z, doppler, snr, noise, track_index`` (positions in m, doppler in
    m/s, snr/noise in dB, track_index 255 = not associated). Fields that were
    not present in the frame are ``None``.
    """

    frame_number: int = 0
    timestamp: float = 0.0  # host receive time (time.time())
    num_detected_obj: int = 0
    subframe_number: int = 0
    version: int = 0
    platform: int = 0
    time_cpu_cycles: int = 0

    points: np.ndarray | None = None
    num_points: int = 0
    tracks: list[Track] | None = None
    track_indexes: np.ndarray | None = None
    range_profile: np.ndarray | None = None
    range_profile_major: np.ndarray | None = None
    range_profile_minor: np.ndarray | None = None
    capon_heatmap: np.ndarray | None = None  # (10, 32, 16) or flat if nonstandard
    micro_doppler: np.ndarray | None = None  # (num_targets, bins) or flat
    micro_doppler_features: list[dict] | None = None
    presence: list[int] | None = None
    classifier_probabilities: np.ndarray | None = None
    stats: ExtStats | None = None

    #: payloads of TLV types nothing was registered for, keyed by type id
    raw_tlvs: dict[int, bytes] = field(default_factory=dict)
    #: user-registered parsers can deposit arbitrary results here
    extras: dict[str, Any] = field(default_factory=dict)
    #: non-fatal parse problems ("tlv 301 truncated", "length mismatch", ...)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors
