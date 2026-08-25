"""Recorders for radar sessions.

Two formats:

* **raw** (``.bin``) — the untouched UART byte stream. Replayable with
  :func:`openwaves.io.replay.replay_raw` and ideal as a parser test fixture.
* **frames** (``.jsonl`` + ``_meta.json``) — one JSON object per parsed
  frame, matching the layout of the recorded sessions under
  ``software/data/fall_detection/data/sessions``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..frames import FrameData


class RawUartRecorder:
    """Append raw frame bytes to a ``.bin`` file."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._fh = self.path.open("wb")
        self.bytes_written = 0

    def write(self, frame_bytes: bytes) -> None:
        self._fh.write(frame_bytes)
        self.bytes_written += len(frame_bytes)

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "RawUartRecorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class FrameRecorder:
    """Write parsed frames as JSON lines plus a metadata sidecar."""

    def __init__(self, path: Path | str, *, metadata: dict | None = None):
        self.path = Path(path)
        self._fh = self.path.open("w")
        self.metadata = dict(metadata or {})
        self.frames_written = 0
        self._t0 = time.time()

    def write(self, frame: FrameData) -> None:
        record: dict = {
            "frame_idx": self.frames_written,
            "frame_number": frame.frame_number,
            "t": frame.timestamp,
        }
        if frame.points is not None:
            n = frame.num_points or len(frame.points)
            record["numPts"] = int(n)
            record["points"] = [
                [round(float(v), 6) for v in row] for row in frame.points[:n]
            ]
        if frame.capon_heatmap is not None:
            record["caponHeatmapShape"] = list(frame.capon_heatmap.shape)
            record["caponHeatmap"] = [
                float(v) for v in frame.capon_heatmap.ravel()
            ]
        if frame.errors:
            record["errors"] = frame.errors
        self._fh.write(json.dumps(record) + "\n")
        self.frames_written += 1

    def close(self) -> None:
        self._fh.close()
        meta = {
            "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._t0)),
            "total_frames": self.frames_written,
            **self.metadata,
        }
        meta_path = self.path.with_name(self.path.stem + "_meta.json")
        meta_path.write_text(json.dumps(meta, indent=2))

    def __enter__(self) -> "FrameRecorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
