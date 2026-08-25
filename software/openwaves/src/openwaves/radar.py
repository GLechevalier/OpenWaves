"""The high-level Radar facade.

Typical use::

    from openwaves import Radar

    with Radar() as radar:
        radar.configure("cfg/Tracking_MidBw.cfg")
        radar.start()
        for frame in radar.frames():
            print(frame.frame_number, frame.num_points)

The facade autodetects the board's COM ports, tells single-port firmware
(the in-repo material-classification image streams TLVs on the CLI UART)
apart from dual-port firmware (TI's Motion-and-Presence demo streams on the
auxiliary data port), sends configurations with all the CLI quirks handled,
and turns the TLV byte stream into typed :class:`~openwaves.frames.FrameData`
objects.
"""

from __future__ import annotations

import logging
import time
from typing import Iterator, Literal

import serial

from .config.model import RadarConfig, SensorStart
from .control.cli import RadarCli
from .exceptions import FrameSyncError, OpenWavesError
from .frames import FrameData
from .tlv.header import sync_and_read_frame
from .tlv.registry import DEFAULT_REGISTRY, TlvRegistry
from .transport.ports import RadarPorts, find_radar_ports

log = logging.getLogger(__name__)

Layout = Literal["auto", "single", "dual"]

DUAL_PORT_DATA_BAUDS = (1250000, 921600)


class Radar:
    """Context-managed access to one IWRL6432BOOST board."""

    def __init__(
        self,
        ports: RadarPorts | None = None,
        *,
        registry: TlvRegistry = DEFAULT_REGISTRY,
        layout: Layout = "auto",
        cli_baudrate: int = 115200,
    ):
        self._given_ports = ports
        self.registry = registry
        self.layout: Layout = layout
        self._cli_baudrate = cli_baudrate

        self.ports: RadarPorts | None = None
        self.cli: RadarCli | None = None
        self._data_ser: serial.Serial | None = None
        self._started = False
        self._sensor_start_line = "sensorStart 0 0 0 0"

    # -- lifecycle -------------------------------------------------------

    def open(self) -> "Radar":
        self.ports = self._given_ports or find_radar_ports()
        log.info("Radar ports: %s", self.ports)
        self.cli = RadarCli(self.ports.cli_port, self._cli_baudrate)
        if self.layout == "auto":
            self._detect_layout()
        return self

    def close(self) -> None:
        if self.cli is not None:
            if self._started:
                try:
                    self.cli.sensor_stop()
                except OpenWavesError:
                    log.warning("sensorStop was not acknowledged on close")
            self.cli.close()
            self.cli = None
        if self._data_ser is not None and self._data_ser.is_open:
            self._data_ser.close()
        self._data_ser = None
        self._started = False

    def __enter__(self) -> "Radar":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def _require_cli(self) -> RadarCli:
        if self.cli is None:
            raise OpenWavesError("Radar is not open — use 'with Radar() as radar:'")
        return self.cli

    def _detect_layout(self) -> None:
        """Probe the firmware to choose single- vs dual-port streaming.

        TI's stock demos answer ``version`` with a platform string
        (``L684x`` on the IWRL6432 MPD demo, which streams on the auxiliary
        data port). Anything else — including the in-repo material
        classification firmware — is treated as single-port.
        """
        response = self._require_cli().probe_version()
        if "L684x" in response or "xWRL6" in response:
            self.layout = "dual"
        else:
            self.layout = "single"
        log.info("Detected %s-port firmware layout", self.layout)

    # -- control ---------------------------------------------------------

    def configure(self, config) -> None:
        """Send a configuration (path, RadarConfig, or iterable of lines).

        ``sensorStart`` lines are held back — call :meth:`start` when you
        are ready to stream (their arguments are remembered and reused).
        """
        cli = self._require_cli()
        if isinstance(config, RadarConfig):
            lines = config.to_lines()
        elif hasattr(config, "read_text") or isinstance(config, str):
            from pathlib import Path

            lines = Path(config).read_text().splitlines()
        else:
            lines = list(config)

        to_send = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("sensorStart"):
                self._sensor_start_line = stripped
                continue
            to_send.append(line)
        cli.send_config(to_send)

    def start(self) -> None:
        """Start the sensor (using the config's sensorStart arguments)."""
        cli = self._require_cli()
        cli.send_command(self._sensor_start_line, timeout=10.0)
        self._started = True
        time.sleep(0.05)
        stream = self._data_stream()
        if hasattr(stream, "reset_input_buffer"):
            stream.reset_input_buffer()

    def stop(self) -> None:
        self._require_cli().sensor_stop()
        self._started = False

    def warm_reset(self, *, redetect: bool = True, settle: float = 3.0) -> None:
        """Reboot the device; optionally re-open it once it re-enumerates."""
        self._require_cli().warm_reset()
        if self._data_ser is not None and self._data_ser.is_open:
            self._data_ser.close()
        self._data_ser = None
        self.cli = None
        self._started = False
        if redetect:
            time.sleep(settle)
            self.open()

    def send_command(self, line: str, **kwargs) -> str:
        """Send a raw CLI command line (see docs/cli-commands.md)."""
        return self._require_cli().send_command(line, **kwargs)

    # -- streaming -------------------------------------------------------

    def _data_stream(self):
        if self.layout == "single":
            return self._require_cli().serial
        if self._data_ser is None or not self._data_ser.is_open:
            assert self.ports is not None
            self._data_ser = serial.Serial(
                self.ports.data_port, DUAL_PORT_DATA_BAUDS[0], timeout=0.1
            )
        return self._data_ser

    def read_frame(self, *, _retry_baud: bool = True) -> FrameData:
        """Block until one complete frame arrives; parse and return it."""
        stream = self._data_stream()
        try:
            raw = sync_and_read_frame(stream)
        except FrameSyncError:
            # A dual-port board that ignored 'baudRate 1250000' streams at
            # 921600 — retry once at the fallback rate.
            if (
                _retry_baud
                and self.layout == "dual"
                and self._data_ser is not None
                and self._data_ser.baudrate != DUAL_PORT_DATA_BAUDS[1]
            ):
                log.info("No frames at %d baud, retrying at %d",
                         self._data_ser.baudrate, DUAL_PORT_DATA_BAUDS[1])
                self._data_ser.baudrate = DUAL_PORT_DATA_BAUDS[1]
                return self.read_frame(_retry_baud=False)
            raise
        return self.registry.parse_frame(raw)

    def frames(self, *, count: int | None = None) -> Iterator[FrameData]:
        """Yield parsed frames until stopped (or ``count`` frames)."""
        yielded = 0
        while count is None or yielded < count:
            yield self.read_frame()
            yielded += 1
