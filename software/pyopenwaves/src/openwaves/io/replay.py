"""Replay raw UART captures without hardware."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Iterator

from ..exceptions import FrameSyncError
from ..frames import FrameData
from ..tlv.header import sync_and_read_frame
from ..tlv.registry import DEFAULT_REGISTRY, TlvRegistry


def replay_raw(
    path: Path | str, *, registry: TlvRegistry = DEFAULT_REGISTRY
) -> Iterator[FrameData]:
    """Yield parsed frames from a raw UART capture (.bin) file."""
    data = Path(path).read_bytes()
    stream = io.BytesIO(data)
    while True:
        try:
            frame_bytes = sync_and_read_frame(stream)
        except FrameSyncError:
            return
        yield registry.parse_frame(frame_bytes)
