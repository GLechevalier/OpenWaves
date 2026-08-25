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
    pip install -e software/pyopenwaves[ble,viz]   (from the repo root)
"""

import asyncio
import logging

import numpy as np

from openwaves.ble import HEATMAP_FLOAT_COUNT, HEATMAP_SHAPE, RadarWallBLEClient

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

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d │ %(levelname)-7s │ %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# RerunVisualizer Class
# ═══════════════════════════════════════════════════════════════════════════════

class RerunVisualizer:
    """
    Handles Rerun initialization and frame logging.
    
    Visualizes 3D heatmap data as 10 separate 2D image slices.
    """

    def __init__(self, application_id: str = "radarwall_visualization"):
        """
        Initialize the Rerun visualizer.
        
        Args:
            application_id: Rerun application identifier
        """
        self.application_id = application_id
        self.initialized = False
        self.frame_count = 0

    def init(self, spawn_viewer: bool = True) -> None:
        """
        Initialize Rerun recording.
        
        Args:
            spawn_viewer: If True, spawn the Rerun viewer automatically
        """
        if not RERUN_AVAILABLE:
            logger.warning("Rerun not available, visualization disabled")
            return

        rr.init(self.application_id, spawn=spawn_viewer)
        
        # Set up the recording
        rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Y_DOWN, static=True)
        
        self.initialized = True
        logger.info(f"🎬 Rerun initialized: {self.application_id}")

    def log_frame(self, heatmap: np.ndarray, frame_number: int, timestamp_ms: int) -> None:
        """
        Log a complete heatmap frame to Rerun.
        
        Args:
            heatmap: Float32 array of shape (5120,) or (10, 16, 32)
            frame_number: Frame number from the radar
            timestamp_ms: Timestamp in milliseconds
        """
        if not self.initialized:
            return

        # Reshape to 3D if needed: (depth=10, height=32, width=16)
        if heatmap.shape == (HEATMAP_FLOAT_COUNT,):
            heatmap_3d = heatmap.reshape(HEATMAP_SHAPE)
        elif heatmap.shape == HEATMAP_SHAPE:
            heatmap_3d = heatmap
        else:
            logger.warning(f"Unexpected heatmap shape: {heatmap.shape}, expected {HEATMAP_SHAPE}")
            return


        rr.set_time("frame", sequence=frame_number)
        rr.set_time("timestamp", timestamp=timestamp_ms / 1000.0)

        # Log the full 3D tensor for reference
        rr.log("radar/heatmap_3d", rr.Tensor(heatmap_3d))

        # Log the range bins evolution
        range_means = heatmap_3d.mean(axis=(1, 2))  # Shape: (10,)
        rr.log("range_bins/profile", rr.BarChart(range_means))

        # Log scalar metrics
        rr.log("metrics/heatmap_mean", rr.Scalars(float(heatmap.mean())))
        rr.log("metrics/heatmap_max", rr.Scalars(float(heatmap.max())))
        rr.log("metrics/heatmap_min", rr.Scalars(float(heatmap.min())))

        self.frame_count += 1
        logger.info(f"📊 Logged frame #{frame_number} to Rerun (total: {self.frame_count})")

    def close(self) -> None:
        """Clean up Rerun resources."""
        if self.initialized:
            logger.info(f"🎬 Rerun session closed ({self.frame_count} frames logged)")
            self.initialized = False



# ═══════════════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("🚀 RadarWall BLE → Rerun Visualizer")
    logger.info("=" * 60)
    
    # Initialize Rerun visualizer
    visualizer = RerunVisualizer(application_id="radarwall_3d_heatmap")
    visualizer.init(spawn_viewer=True)
    
    # Create callback for complete frames
    def on_frame_complete(heatmap: np.ndarray, frame_number: int, timestamp_ms: int):
        visualizer.log_frame(heatmap, frame_number, timestamp_ms)
    
    # Initialize BLE client
    ble_client = RadarWallBLEClient(on_frame_complete=on_frame_complete)
    
    try:
        # Connect to device
        if not await ble_client.connect():
            logger.error("Failed to connect to RadarWall")
            return
        
        # Start recording
        await ble_client.start_recording()
        
        # Run until interrupted
        logger.info("📡 Receiving data... Press Ctrl+C to stop")
        
        while True:
            await asyncio.sleep(1.0)
            
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise
    finally:
        # Cleanup
        await ble_client.disconnect()
        visualizer.close()
        logger.info("👋 Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())