"""Flash protocol tests against a scripted fake bootloader."""

import struct

import pytest

from openwaves.exceptions import FlashError
from openwaves.flash.protocol import (
    ACK,
    NACK,
    OPCODE_FILE_CLOSE,
    OPCODE_GET_LAST_STATUS,
    OPCODE_PING,
    OPCODE_SEND_DATA,
    OPCODE_START_DOWNLOAD,
    SYNC,
    BootloaderClient,
    FileId,
    Storage,
)


class FakeBootloaderSerial:
    """In-memory serial double implementing the device side of the protocol."""

    def __init__(self, *, nack_opcodes=(), status_code=0xDEAD):
        self.is_open = True
        self.break_condition = False
        self.timeout = 1.0
        self._rx = bytearray()  # bytes queued for the host to read
        self._pending = bytearray()  # bytes written by the host, not yet framed
        self.received_packets: list[bytes] = []
        self.nack_opcodes = set(nack_opcodes)
        self.status_code = status_code
        self.flash = bytearray()
        self._download_size = None
        self._queue_ack()  # connect handshake: ROM acks on break

    # -- device behaviour ------------------------------------------------

    def _queue_ack(self, ok=True):
        self._rx += bytes([0x00, 0x02, 0x00, 0x00, ACK if ok else NACK])

    def _queue_response(self, payload: bytes):
        self._rx += struct.pack(">HB", len(payload) + 2, sum(payload) & 0xFF) + payload

    def _process_packets(self):
        while True:
            if len(self._pending) < 4 or self._pending[0] != SYNC:
                return
            size = struct.unpack(">H", self._pending[1:3])[0]
            payload_len = size - 2
            if len(self._pending) < 4 + payload_len:
                return
            checksum = self._pending[3]
            payload = bytes(self._pending[4 : 4 + payload_len])
            del self._pending[: 4 + payload_len]
            assert sum(payload) & 0xFF == checksum, "host sent bad checksum"
            self.received_packets.append(payload)
            self._handle(payload)

    def _handle(self, payload: bytes):
        opcode = payload[0]
        if opcode in self.nack_opcodes:
            self._queue_ack(ok=False)
            return
        if opcode == OPCODE_GET_LAST_STATUS:
            self._queue_ack()
            self._queue_response(self.status_code.to_bytes(8, "little"))
        elif opcode == OPCODE_START_DOWNLOAD:
            self._download_size = struct.unpack(">I", payload[1:5])[0]
            self.flash.clear()
            self._queue_ack()
        elif opcode == OPCODE_SEND_DATA:
            self.flash += payload[1:]
            self._queue_ack()
        elif opcode == OPCODE_FILE_CLOSE:
            self._queue_ack()
        elif opcode == OPCODE_PING:
            self._queue_ack()
        else:
            self._queue_ack()

    # -- pyserial surface -------------------------------------------------

    def write(self, data: bytes):
        self._pending += data
        self._process_packets()
        return len(data)

    def read(self, n: int) -> bytes:
        out = bytes(self._rx[:n])
        del self._rx[:n]
        return out

    def reset_input_buffer(self):
        self._rx.clear()

    def close(self):
        self.is_open = False


@pytest.fixture
def client(monkeypatch):
    def make(**kwargs):
        fake = FakeBootloaderSerial(**kwargs)
        c = BootloaderClient("FAKE")
        monkeypatch.setattr(c, "_open", lambda timeout=5.0: fake)
        c._ser = fake
        return c, fake

    return make


def test_connect_and_ping(client):
    c, fake = client()
    c.connect(timeout=1.0)
    assert fake.break_condition is False  # released after handshake
    assert c.ping()


def test_download_file_chunks_and_content(client, tmp_path):
    c, fake = client()
    c.connect(timeout=1.0)
    image = tmp_path / "fw.appimage"
    payload = bytes(range(256)) * 3  # 768 bytes -> 240+240+240+48
    image.write_bytes(payload)
    progress_calls = []
    c.download_file(
        image,
        FileId.META_IMAGE1,
        Storage.SFLASH,
        progress=lambda sent, total: progress_calls.append((sent, total)),
    )
    assert bytes(fake.flash) == payload
    assert fake._download_size == len(payload)
    chunk_packets = [p for p in fake.received_packets if p[0] == OPCODE_SEND_DATA]
    assert [len(p) - 1 for p in chunk_packets] == [240, 240, 240, 48]
    assert progress_calls[-1] == (768, 768)
    start = next(p for p in fake.received_packets if p[0] == OPCODE_START_DOWNLOAD)
    assert struct.unpack(">I", start[5:9])[0] == int(Storage.SFLASH)
    assert struct.unpack(">I", start[9:13])[0] == int(FileId.META_IMAGE1)


def test_nack_raises_with_status_code(client, tmp_path):
    c, fake = client(nack_opcodes={OPCODE_START_DOWNLOAD}, status_code=0x123456)
    c.connect(timeout=1.0)
    image = tmp_path / "fw.appimage"
    image.write_bytes(b"x" * 100)
    with pytest.raises(FlashError) as exc:
        c.download_file(image)
    assert exc.value.code == 0x123456


def test_empty_file_rejected(client, tmp_path):
    c, _ = client()
    image = tmp_path / "empty.appimage"
    image.write_bytes(b"")
    with pytest.raises(FlashError):
        c.download_file(image)
