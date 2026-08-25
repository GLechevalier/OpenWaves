"""Frame header parsing and stream synchronisation."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from ..exceptions import FrameSyncError
from .defines import FRAME_HEADER_SIZE, FRAME_HEADER_STRUCT, MAGIC_WORD


@dataclass(frozen=True)
class FrameHeader:
    """The 40-byte header at the start of every UART frame."""

    version: int
    total_packet_len: int
    platform: int
    frame_number: int
    time_cpu_cycles: int
    num_detected_obj: int
    num_tlvs: int
    subframe_number: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "FrameHeader":
        if len(data) < FRAME_HEADER_SIZE:
            raise ValueError(
                f"Frame header needs {FRAME_HEADER_SIZE} bytes, got {len(data)}"
            )
        (
            magic,
            version,
            total_packet_len,
            platform,
            frame_number,
            time_cpu_cycles,
            num_detected_obj,
            num_tlvs,
            subframe_number,
        ) = struct.unpack(FRAME_HEADER_STRUCT, data[:FRAME_HEADER_SIZE])
        if magic != int.from_bytes(MAGIC_WORD, "little"):
            raise ValueError(f"Bad magic word: 0x{magic:016x}")
        return cls(
            version=version,
            total_packet_len=total_packet_len,
            platform=platform,
            frame_number=frame_number,
            time_cpu_cycles=time_cpu_cycles,
            num_detected_obj=num_detected_obj,
            num_tlvs=num_tlvs,
            subframe_number=subframe_number,
        )


def sync_and_read_frame(stream, *, max_scan: int = 1 << 20) -> bytes:
    """Read one complete frame from a byte stream (serial port or file).

    Scans byte-by-byte for the 8-byte magic word, then reads the rest of the
    frame using ``totalPacketLen`` from the header. ``stream`` needs a
    ``read(n)`` method; a pyserial port with a timeout works — on timeout
    with no data a :class:`FrameSyncError` is raised so callers can decide
    whether to retry.

    Returns the full frame bytes (magic word included).
    """
    index = 0
    scanned = 0
    frame = bytearray()
    empty_reads = 0
    while True:
        byte = stream.read(1)
        if not byte:
            empty_reads += 1
            if empty_reads > 50:
                raise FrameSyncError(
                    "No data while searching for the frame magic word "
                    "(sensor not started, or wrong port/baudrate?)"
                )
            continue
        empty_reads = 0
        scanned += 1
        if scanned > max_scan:
            raise FrameSyncError(f"Magic word not found in {max_scan} bytes")
        if byte[0] == MAGIC_WORD[index]:
            frame.append(byte[0])
            index += 1
            if index == len(MAGIC_WORD):
                break
        else:
            index = 0
            frame.clear()
            if byte[0] == MAGIC_WORD[0]:
                frame.append(byte[0])
                index = 1

    # Magic found: read version (4) + totalPacketLen (4)
    rest_of_lengths = _read_exact(stream, 8)
    frame += rest_of_lengths
    total_packet_len = int.from_bytes(rest_of_lengths[4:8], "little")
    if total_packet_len < FRAME_HEADER_SIZE or total_packet_len > (1 << 24):
        raise FrameSyncError(f"Implausible totalPacketLen {total_packet_len}")
    frame += _read_exact(stream, total_packet_len - len(frame))
    return bytes(frame)


def _read_exact(stream, n: int) -> bytes:
    buf = bytearray()
    tries = 0
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            tries += 1
            if tries > 50:
                raise FrameSyncError(
                    f"Timeout mid-frame: expected {n} bytes, got {len(buf)}"
                )
            continue
        tries = 0
        buf += chunk
    return bytes(buf)
