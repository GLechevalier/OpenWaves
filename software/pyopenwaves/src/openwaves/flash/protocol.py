"""Clean-room implementation of the xWRL6432 ROM UART bootloader protocol.

With the board's SOP switches in flash mode (SOP_MODE1) the ROM bootloader
listens on the Application/User UART at 115200 baud. The host protocol:

* **Packet (host → device)**: ``0xAA`` sync byte, big-endian ``uint16``
  packet size (payload length + 2), ``uint8`` checksum (byte-sum of the
  payload, masked to 8 bits), then the payload. The payload's first byte is
  an opcode.
* **Acknowledge (device → host)**: 2 size bytes, 1 checksum byte, a ``0x00``
  filler, then ``0xCC`` (ACK) or ``0x33`` (NACK).
* **Response packet (device → host)**: big-endian ``uint16`` size (payload
  + 2) and ``uint8`` checksum, then the payload.
* **Connect**: the host holds a UART break while the device powers up; the
  autobauding ROM answers with an ACK.
* **Download**: START_DOWNLOAD (file size, storage id, file id, mirror flag,
  all big-endian uint32), then the image in 240-byte SEND_DATA chunks, then
  FILE_CLOSE. On NACK the host asks GET_LAST_STATUS for a 64-bit
  little-endian status code.

This module is an original implementation written from the protocol facts
above; it contains no TI code.
"""

from __future__ import annotations

import enum
import logging
import struct
import time
from pathlib import Path
from typing import Callable

import serial

from ..exceptions import FlashError

log = logging.getLogger(__name__)

SYNC = 0xAA
ACK = 0xCC
NACK = 0x33

OPCODE_PING = 0x20
OPCODE_START_DOWNLOAD = 0x21
OPCODE_FILE_CLOSE = 0x22
OPCODE_GET_LAST_STATUS = 0x23
OPCODE_SEND_DATA = 0x24
OPCODE_SEND_DATA_RAM = 0x26
OPCODE_DISCONNECT = 0x27
OPCODE_ERASE = 0x28
OPCODE_GET_VERSION_INFO = 0x2F

CHUNK_SIZE = 240
MAX_FILE_SIZE = 1024 * 1024
BOOTLOADER_BAUD = 115200
STATUS_SIZE = 8  # GET_LAST_STATUS payload bytes


class FileId(enum.IntEnum):
    BSS_BUILD = 0
    CALIB_DATA = 1
    CONFIG_INFO = 2
    MSS_BUILD = 3
    META_IMAGE1 = 4
    META_IMAGE2 = 5
    META_IMAGE3 = 6
    META_IMAGE4 = 7


class Storage(enum.IntEnum):
    SDRAM = 0
    FLASH = 1
    SFLASH = 2
    EEPROM = 3
    SRAM = 4


class BootloaderClient:
    """Talks the ROM UART bootloader on one serial port.

    Typical use::

        client = BootloaderClient("COM4")
        client.connect()             # hold break; user power-cycles the board
        client.download_file(Path("firmware.appimage"))
        client.close()
    """

    def __init__(self, port: str, baudrate: int = BOOTLOADER_BAUD):
        self.port = port
        self.baudrate = baudrate
        self._ser: serial.Serial | None = None

    # -- port management -------------------------------------------------

    def _open(self, timeout: float = 5.0) -> serial.Serial:
        if self._ser is None or not self._ser.is_open:
            self._ser = serial.Serial(self.port, self.baudrate, timeout=timeout)
            self._ser.reset_input_buffer()
        else:
            self._ser.timeout = timeout
        return self._ser

    def close(self) -> None:
        if self._ser is not None and self._ser.is_open:
            self._ser.close()
        self._ser = None

    def __enter__(self) -> "BootloaderClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- framing ---------------------------------------------------------

    def _send_packet(self, payload: bytes) -> None:
        ser = self._open()
        checksum = sum(payload) & 0xFF
        ser.write(bytes([SYNC]) + struct.pack(">H", len(payload) + 2) + bytes([checksum]))
        ser.write(payload)

    def _read_ack(self, timeout: float | None = None) -> bool:
        ser = self._open(timeout if timeout is not None else 5.0)
        # 2 size bytes + 1 checksum + 1 filler precede the ack byte
        header = ser.read(4)
        if len(header) < 4:
            raise FlashError(
                "No answer from the bootloader — check that the SOP switches "
                "are in flash mode (SOP_MODE1) and the board was power-cycled."
            )
        deadline = time.monotonic() + (timeout if timeout is not None else 5.0)
        while time.monotonic() < deadline:
            byte = ser.read(1)
            if not byte:
                continue
            if byte[0] == ACK:
                return True
            if byte[0] == NACK:
                return False
        raise FlashError("Timed out waiting for ACK/NACK")

    def _receive_packet(self, expected_length: int) -> bytes:
        ser = self._open()
        header = ser.read(3)
        if len(header) < 3:
            raise FlashError("Timeout reading response header")
        packet_length, checksum = struct.unpack(">HB", header)
        packet_length -= 2
        payload = ser.read(packet_length)
        if len(payload) != packet_length:
            raise FlashError(
                f"Timeout reading response payload ({len(payload)}/{packet_length} bytes)"
            )
        if expected_length and packet_length != expected_length:
            raise FlashError(
                f"Unexpected response length {packet_length} (expected {expected_length})"
            )
        if sum(payload) & 0xFF != checksum:
            raise FlashError("Checksum mismatch on response packet")
        return payload

    def _read_last_status(self) -> int:
        self._send_packet(bytes([OPCODE_GET_LAST_STATUS]))
        self._read_ack()
        payload = self._receive_packet(STATUS_SIZE)
        return int.from_bytes(payload, "little")

    def _command(self, payload: bytes, what: str) -> None:
        """Send a command; on NACK fetch the status code and raise."""
        self._send_packet(payload)
        if not self._read_ack():
            code = None
            try:
                code = self._read_last_status()
            except FlashError:
                pass
            raise FlashError(f"Bootloader refused {what}", code=code)

    # -- public API ------------------------------------------------------

    def connect(
        self,
        timeout: float = 30.0,
        on_waiting: Callable[[], None] | None = None,
    ) -> None:
        """Hold a UART break and wait for the ROM's ACK.

        The break must be asserted while the device boots, so power-cycle
        (or reset) the board *after* this call starts waiting. ``on_waiting``
        is called once when the wait begins (e.g. to prompt the user).
        """
        ser = self._open(timeout)
        ser.break_condition = True
        time.sleep(0.1)
        if on_waiting:
            on_waiting()
        try:
            if not self._read_ack(timeout=timeout):
                raise FlashError("Bootloader NACKed the connection attempt")
        finally:
            ser.break_condition = False
        log.info("Bootloader connected on %s", self.port)

    def ping(self) -> bool:
        self._send_packet(bytes([OPCODE_PING]))
        return self._read_ack()

    def get_version(self) -> bytes:
        """Raw 12-byte ROM version blob."""
        self._send_packet(bytes([OPCODE_GET_VERSION_INFO]))
        if not self._read_ack():
            raise FlashError("GET_VERSION was NACKed")
        ser = self._open()
        ser.read(3)  # response size + checksum
        return ser.read(12)

    def erase_storage(
        self, storage: Storage = Storage.SFLASH, offset: int = 0, capacity: int = 0
    ) -> None:
        payload = (
            bytes([OPCODE_ERASE])
            + struct.pack(">I", int(storage))
            + struct.pack(">I", offset)
            + struct.pack(">I", capacity)
        )
        self._send_packet(payload)
        if not self._read_ack(timeout=60.0):
            raise FlashError("Erase was NACKed")
        log.info("Storage %s erased", storage.name)

    def download_file(
        self,
        path: Path,
        file_id: FileId = FileId.META_IMAGE1,
        storage: Storage = Storage.SFLASH,
        *,
        mirror_enabled: bool = False,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Write ``path`` into the given bootloader file slot.

        ``progress(bytes_sent, total_bytes)`` is called after each chunk.
        """
        data = Path(path).read_bytes()
        size = len(data)
        if not 0 < size < MAX_FILE_SIZE:
            raise FlashError(f"Invalid file size {size} for {path}")

        start = (
            bytes([OPCODE_START_DOWNLOAD])
            + struct.pack(">I", size)
            + struct.pack(">I", int(storage))
            + struct.pack(">I", int(file_id))
            + struct.pack(">I", 1 if mirror_enabled else 0)
        )
        self._command(start, "START_DOWNLOAD")

        chunk_opcode = OPCODE_SEND_DATA_RAM if storage == Storage.SRAM else OPCODE_SEND_DATA
        sent = 0
        while sent < size:
            chunk = data[sent : sent + CHUNK_SIZE]
            self._command(bytes([chunk_opcode]) + chunk, f"chunk at offset {sent}")
            sent += len(chunk)
            if progress:
                progress(sent, size)

        close = bytes([OPCODE_FILE_CLOSE]) + struct.pack(">I", int(file_id))
        if storage == Storage.SRAM:
            # SRAM close: ack then an 8-byte status packet follows directly.
            self._send_packet(close)
            self._read_ack()
            status = int.from_bytes(self._receive_packet(STATUS_SIZE), "little")
            if status != 0:
                raise FlashError("SRAM download failed", code=status)
        else:
            self._command(close, "FILE_CLOSE")
        log.info("Downloaded %s (%d bytes) to %s/%s", path, size, storage.name, file_id.name)

    def disconnect(self) -> None:
        try:
            self._send_packet(bytes([OPCODE_DISCONNECT]))
        finally:
            self.close()
