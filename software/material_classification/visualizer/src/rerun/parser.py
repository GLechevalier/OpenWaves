#!/usr/bin/env python3
"""
RadarWall BLE to Rerun Visualizer

This script connects to a RadarWall ESP32 device via BLE, receives radar heatmap
data (Capon 3D beamforming), and visualizes it in real-time using Rerun.

Architecture:
- RadarWallBLEClient: Handles BLE connection, binary protocol parsing, chunk reassembly
- RerunVisualizer: Manages Rerun initialization and frame logging

Usage:
    python radarwall_rerun.py

Requirements:
    pip install bleak rerun-sdk numpy
"""

import asyncio
import struct
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional
from collections import defaultdict

import numpy as np
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

# Optional: import rerun only when needed
try:
    import rerun as rr
    RERUN_AVAILABLE = True
except ImportError:
    RERUN_AVAILABLE = False
    print("Warning: rerun-sdk not installed. Visualization disabled.")

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

# BLE Configuration
DEVICE_NAME = "RadarWall"
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
DATA_CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
COMMAND_CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a9"

# Protocol Configuration
FRAME_HEADER_SIZE = 16  # bytes
CHUNK_HEADER_SIZE = 12  # bytes
MAX_CHUNK_PAYLOAD_SIZE = 500  # bytes (MTU 512 - 12 header)

# Heatmap Configuration
HEATMAP_FLOAT_COUNT = 5120
HEATMAP_SHAPE = (10, 32, 16)  # (depth, height, width) - 10 slices of 16x32

# Timeout Configuration
PACKET_TIMEOUT_MS = 50  # ms since last new chunk before requesting resend
TRANSMISSION_TIMEOUT_MS = 10000  # ms total timeout for a frame
MAX_RETRIES = 3

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d │ %(levelname)-7s │ %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FrameHeader:
    """Binary frame header (16 bytes)."""
    frame_number: int
    timestamp_ms: int
    data_type: int
    total_chunks: int
    total_size: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "FrameHeader":
        """Parse frame header from 16 bytes (little-endian)."""
        if len(data) < FRAME_HEADER_SIZE:
            raise ValueError(f"Frame header too short: {len(data)} < {FRAME_HEADER_SIZE}")
        
        frame_number, timestamp_ms, data_type, total_chunks, total_size = struct.unpack(
            "<IIHHI", data[:FRAME_HEADER_SIZE]
        )
        return cls(
            frame_number=frame_number,
            timestamp_ms=timestamp_ms,
            data_type=data_type,
            total_chunks=total_chunks,
            total_size=total_size,
        )

    def __repr__(self) -> str:
        return (
            f"FrameHeader(frame={self.frame_number}, ts={self.timestamp_ms}ms, "
            f"chunks={self.total_chunks}, size={self.total_size}B)"
        )


@dataclass
class ChunkHeader:
    """Binary chunk header (12 bytes)."""
    chunk_index: int
    chunk_size: int
    frame_number: int
    checksum: int
    reserved: int  # 0x01 = resend flag

    @classmethod
    def from_bytes(cls, data: bytes) -> "ChunkHeader":
        """Parse chunk header from 12 bytes (little-endian)."""
        if len(data) < CHUNK_HEADER_SIZE:
            raise ValueError(f"Chunk header too short: {len(data)} < {CHUNK_HEADER_SIZE}")
        
        chunk_index, chunk_size, frame_number, checksum, reserved = struct.unpack(
            "<HHIHH", data[:CHUNK_HEADER_SIZE]
        )
        return cls(
            chunk_index=chunk_index,
            chunk_size=chunk_size,
            frame_number=frame_number,
            checksum=checksum,
            reserved=reserved,
        )

    @property
    def is_resend(self) -> bool:
        return self.reserved == 0x01


@dataclass
class FrameState:
    """State for a frame being assembled."""
    header: FrameHeader
    chunks: dict[int, bytes] = field(default_factory=dict)
    last_update_ms: float = 0.0
    retry_count: int = 0

    def is_complete(self) -> bool:
        """Check if all chunks have been received."""
        return len(self.chunks) == self.header.total_chunks

    def get_missing_chunks(self) -> list[int]:
        """Get list of missing chunk indices."""
        return [i for i in range(self.header.total_chunks) if i not in self.chunks]

    def reconstruct_heatmap(self) -> np.ndarray:
        """Reassemble chunks into a float32 array."""
        buffer = bytearray(self.header.total_size)
        offset = 0
        
        for i in range(self.header.total_chunks):
            chunk = self.chunks.get(i)
            if chunk is None:
                raise ValueError(f"Missing chunk {i} during reconstruction")
            buffer[offset:offset + len(chunk)] = chunk
            offset += len(chunk)
        
        # Convert to float32 array
        heatmap = np.frombuffer(bytes(buffer), dtype=np.float32)
        return heatmap


# ═══════════════════════════════════════════════════════════════════════════════
# RadarWallBLEClient Class
# ═══════════════════════════════════════════════════════════════════════════════

class RadarWallBLEClient:
    """
    BLE client for RadarWall ESP32 device.
    
    Handles connection, binary protocol parsing, chunk reassembly,
    and missing chunk retransmission requests.
    """

    def __init__(self, on_frame_complete: Optional[Callable[[np.ndarray, int, int], None]] = None):
        """
        Initialize the BLE client.
        
        Args:
            on_frame_complete: Callback function(heatmap, frame_number, timestamp_ms)
                              called when a complete frame is received
        """
        self.client: Optional[BleakClient] = None
        self.device_address: Optional[str] = None
        self.on_frame_complete = on_frame_complete
        
        # Frame assembly state
        self.active_frames: dict[int, FrameState] = {}
        self.completed_frame_numbers: set[int] = set()
        
        # Timing
        self._last_packet_time_ms: float = 0.0
        self._recording: bool = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def scan_for_device(self, timeout: float = 10.0) -> Optional[str]:
        """
        Scan for RadarWall device.
        
        Args:
            timeout: Scan timeout in seconds
            
        Returns:
            Device address if found, None otherwise
        """
        logger.info(f"🔍 Scanning for '{DEVICE_NAME}'...")
        
        devices = await BleakScanner.discover(timeout=timeout)
        
        for device in devices:
            if device.name and DEVICE_NAME in device.name:
                logger.info(f"✅ Found: {device.name} ({device.address})")
                return device.address
        
        logger.error(f"❌ Device '{DEVICE_NAME}' not found")
        return None

    async def connect(self, address: Optional[str] = None) -> bool:
        """
        Connect to the RadarWall device.
        
        Args:
            address: Device address (if None, will scan for device)
            
        Returns:
            True if connected successfully
        """
        if address is None:
            address = await self.scan_for_device()
            if address is None:
                return False
        
        self.device_address = address
        
        try:
            logger.info(f"🔗 Connecting to {address}...")
            self.client = BleakClient(address)
            await self.client.connect()
            
            if not self.client.is_connected:
                logger.error("❌ Connection failed")
                return False
            
            logger.info(f"✅ Connected to RadarWall")
            
            # Subscribe to notifications
            await self.client.start_notify(
                DATA_CHARACTERISTIC_UUID,
                self._handle_notification
            )
            logger.info("👂 Subscribed to data notifications")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        await self.stop_recording()
        
        if self.client and self.client.is_connected:
            await self.client.stop_notify(DATA_CHARACTERISTIC_UUID)
            await self.client.disconnect()
            logger.info("🔌 Disconnected from RadarWall")
        
        self.client = None

    async def send_command(self, command: str) -> None:
        """
        Send a command to the ESP32.
        
        Args:
            command: Command string (START, RECORD, STOP, RESEND:...)
        """
        if not self.client or not self.client.is_connected:
            raise RuntimeError("Not connected to device")
        
        data = command.encode('utf-8')
        await self.client.write_gatt_char(COMMAND_CHARACTERISTIC_UUID, data)
        logger.debug(f"📤 Sent command: {command}")

    async def start_recording(self) -> None:
        """Start continuous recording mode."""
        if not self.client or not self.client.is_connected:
            raise RuntimeError("Not connected to device")
        
        self._recording = True
        self.active_frames.clear()
        self.completed_frame_numbers.clear()
        self._last_packet_time_ms = self._current_time_ms()
        
        # Start the monitoring task
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        # Send RECORD command
        await self.send_command("RECORD")
        logger.info("🎥 Recording started")

    async def stop_recording(self) -> None:
        """Stop recording mode."""
        if not self._recording:
            return
        
        self._recording = False
        
        # Cancel monitor task
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        # Send STOP command
        if self.client and self.client.is_connected:
            await self.send_command("STOP")
        
        logger.info("⏹️  Recording stopped")

    def _current_time_ms(self) -> float:
        """Get current time in milliseconds."""
        return asyncio.get_event_loop().time() * 1000

    def _handle_notification(self, sender: BleakGATTCharacteristic, data: bytearray) -> None:
        """
        Handle incoming BLE notification.
        
        This is called by bleak for each notification received.
        """
        if not self._recording:
            return
        
        data = bytes(data)
        data_len = len(data)
        
        # Update last packet time
        self._last_packet_time_ms = self._current_time_ms()
        
        # Check for JSON response (short packet < 12 bytes)
        if data_len < CHUNK_HEADER_SIZE:
            self._handle_json_response(data)
            return
        
        # Frame header (exactly 16 bytes, and we don't have a header for this yet)
        if data_len == FRAME_HEADER_SIZE:
            self._handle_frame_header(data)
            return
        
        # Data chunk (> 12 bytes)
        if data_len > CHUNK_HEADER_SIZE:
            self._handle_chunk(data)
            return

    def _handle_json_response(self, data: bytes) -> None:
        """Handle short JSON response from ESP32."""
        try:
            text = data.decode('utf-8')
            logger.debug(f"📨 JSON response: {text}")
        except UnicodeDecodeError:
            pass

    def _handle_frame_header(self, data: bytes) -> None:
        """Handle incoming frame header."""
        try:
            header = FrameHeader.from_bytes(data)
        except ValueError as e:
            logger.warning(f"⚠️  Invalid frame header: {e}")
            return
        
        frame_num = header.frame_number
        
        # Skip if already completed
        if frame_num in self.completed_frame_numbers:
            logger.debug(f"⏭️  Frame #{frame_num} already completed, header ignored")
            return
        
        # Create new frame state if doesn't exist
        if frame_num not in self.active_frames:
            # Limit active frames to prevent memory issues
            if len(self.active_frames) >= 5:
                oldest = min(self.active_frames.keys())
                del self.active_frames[oldest]
                logger.warning(f"⚠️  Too many active frames, dropped #{oldest}")
            
            self.active_frames[frame_num] = FrameState(
                header=header,
                last_update_ms=self._current_time_ms()
            )
            logger.info(f"📦 Frame #{frame_num} header received ({header.total_chunks} chunks expected)")
        else:
            logger.debug(f"📦 Frame #{frame_num} header duplicate, ignored")

    def _handle_chunk(self, data: bytes) -> None:
        """Handle incoming data chunk."""
        try:
            chunk_header = ChunkHeader.from_bytes(data)
        except ValueError as e:
            logger.warning(f"⚠️  Invalid chunk header: {e}")
            return
        
        frame_num = chunk_header.frame_number
        
        # Skip if frame already completed
        if frame_num in self.completed_frame_numbers:
            return
        
        # Check if we have the frame header
        if frame_num not in self.active_frames:
            logger.debug(f"⚠️  Chunk for unknown frame #{frame_num}, ignored")
            return
        
        frame_state = self.active_frames[frame_num]
        
        # Validate chunk size
        if chunk_header.chunk_size > MAX_CHUNK_PAYLOAD_SIZE:
            logger.warning(f"⚠️  Chunk size too large: {chunk_header.chunk_size}")
            return
        
        # Extract payload
        payload = data[CHUNK_HEADER_SIZE:CHUNK_HEADER_SIZE + chunk_header.chunk_size]
        
        # Store chunk if not already present
        if chunk_header.chunk_index not in frame_state.chunks:
            frame_state.chunks[chunk_header.chunk_index] = payload
            frame_state.last_update_ms = self._current_time_ms()
            
            resend_flag = " (resend)" if chunk_header.is_resend else ""
            logger.debug(
                f"📥 Frame #{frame_num}: chunk {chunk_header.chunk_index + 1}/"
                f"{frame_state.header.total_chunks}{resend_flag}"
            )
        
        # Check if frame is complete
        if frame_state.is_complete():
            self._complete_frame(frame_num)

    def _complete_frame(self, frame_num: int) -> None:
        """Process a completed frame."""
        if frame_num not in self.active_frames:
            return
        
        frame_state = self.active_frames[frame_num]
        
        try:
            heatmap = frame_state.reconstruct_heatmap()
        except ValueError as e:
            logger.error(f"❌ Frame #{frame_num} reconstruction failed: {e}")
            del self.active_frames[frame_num]
            return
        
        logger.info(
            f"✅ Frame #{frame_num} complete ({len(heatmap)} floats, "
            f"{frame_state.header.total_chunks} chunks)"
        )
        
        # Mark as completed
        self.completed_frame_numbers.add(frame_num)
        del self.active_frames[frame_num]
        
        # Keep only recent completed frame numbers (prevent memory leak)
        if len(self.completed_frame_numbers) > 100:
            oldest = min(self.completed_frame_numbers)
            self.completed_frame_numbers.remove(oldest)
        
        # Invoke callback
        if self.on_frame_complete:
            self.on_frame_complete(
                heatmap,
                frame_state.header.frame_number,
                frame_state.header.timestamp_ms
            )

    async def _monitor_loop(self) -> None:
        """Background task to monitor for missing chunks and request resends."""
        while self._recording:
            await asyncio.sleep(0.05)  # Check every 50ms
            
            current_time = self._current_time_ms()
            
            for frame_num, frame_state in list(self.active_frames.items()):
                time_since_update = current_time - frame_state.last_update_ms
                
                # Check if we're stuck
                if time_since_update >= PACKET_TIMEOUT_MS:
                    missing = frame_state.get_missing_chunks()
                    
                    if missing:
                        frame_state.retry_count += 1
                        
                        if frame_state.retry_count > MAX_RETRIES:
                            logger.warning(
                                f"❌ Frame #{frame_num} abandoned after {MAX_RETRIES} retries "
                                f"({len(missing)} chunks missing)"
                            )
                            del self.active_frames[frame_num]
                            continue
                        
                        logger.info(
                            f"🔄 Frame #{frame_num}: requesting {len(missing)} missing chunks "
                            f"(retry {frame_state.retry_count})"
                        )
                        
                        await self._request_missing_chunks(frame_num, missing)
                        frame_state.last_update_ms = current_time
                
                # Clean up very old frames (> transmission timeout)
                total_age = current_time - frame_state.last_update_ms
                if total_age > TRANSMISSION_TIMEOUT_MS:
                    logger.warning(f"🗑️  Frame #{frame_num} timed out, abandoned")
                    del self.active_frames[frame_num]

    async def _request_missing_chunks(self, frame_num: int, missing: list[int]) -> None:
        """Send RESEND command for missing chunks."""
        if not missing:
            return
        
        # Limit to 50 chunks per request (ESP32 limitation)
        missing = missing[:50]
        
        chunk_list = ",".join(str(i) for i in missing)
        command = f"RESEND:{frame_num}:{chunk_list}"
        
        await self.send_command(command)


