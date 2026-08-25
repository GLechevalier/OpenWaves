"""Compatibility helpers for code written against TI's radar_toolbox parser.

TI's ``parseFrame.parseStandardFrame`` returned a loosely-typed dict; the
OpenWaves examples were originally written against it. ``frame_to_output_dict``
converts an :class:`openwaves.frames.FrameData` into that dict layout so
existing consumers keep working unchanged.
"""

from __future__ import annotations

import numpy as np

from .frames import FrameData


def frame_to_output_dict(frame: FrameData) -> dict:
    """Convert a FrameData to the TI-style ``outputDict``.

    Keys produced (when the corresponding data is present): ``error``,
    ``frameNum``, ``pointCloud`` (N, 7), ``numDetectedPoints``,
    ``numDetectedTracks``, ``trackData`` (N, 16), ``trackIndexes``,
    ``microDopplerOutput``, ``numTargets``, ``caponSpectrum3DHeatmap``,
    ``caponSpectrumSize``.
    """
    out: dict = {
        "error": 0 if frame.ok else 1,
        "frameNum": frame.frame_number,
    }

    if frame.points is not None:
        out["pointCloud"] = frame.points
        out["numDetectedPoints"] = frame.num_points
    else:
        out["pointCloud"] = np.zeros((0, 7), np.float64)
        out["numDetectedPoints"] = 0

    if frame.tracks is not None:
        n = len(frame.tracks)
        track_data = np.zeros((n, 16))
        for i, t in enumerate(frame.tracks):
            track_data[i, 0] = t.track_id
            track_data[i, 1:4] = t.position
            track_data[i, 4:7] = t.velocity
            track_data[i, 7:10] = t.acceleration
            track_data[i, 10] = t.g
            track_data[i, 11] = t.confidence
        out["numDetectedTracks"] = n
        out["trackData"] = track_data

    if frame.track_indexes is not None:
        out["trackIndexes"] = frame.track_indexes

    if frame.micro_doppler is not None:
        out["microDopplerOutput"] = frame.micro_doppler
        out["microDopplerNumFloats"] = int(frame.micro_doppler.size)
    if frame.micro_doppler_features is not None:
        out["microDopplerFeatures"] = frame.micro_doppler_features
        out["numTargets"] = len(frame.micro_doppler_features)
    elif frame.tracks is not None:
        out["numTargets"] = len(frame.tracks)

    if frame.capon_heatmap is not None:
        out["caponSpectrum3DHeatmap"] = frame.capon_heatmap
        out["caponSpectrumSize"] = int(frame.capon_heatmap.size)

    if frame.range_profile is not None:
        out["rangeProfile"] = frame.range_profile
    if frame.presence is not None:
        out["enhancedPresenceDet"] = frame.presence

    return out
