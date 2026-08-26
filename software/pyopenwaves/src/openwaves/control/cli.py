"""The mmWave CLI (command) side of the radar's UART link.

Encapsulates every quirk of the IWRL6432 demo CLI:

* commands are echoed, answered with ``Done`` (or ``Error ...``) and a new
  ``mmwDemo:/>`` prompt;
* the ``baudRate <n>`` command re-inits the firmware UART at the new rate,
  so the host must reopen its side right after the command is acknowledged;
* at high baud (1250000) the firmware's UART RX drops characters when they
  arrive back-to-back — every write must go out char-by-char with a ~1 ms
  gap (the same workaround TI's tools use);
* ``sensorWarmRst 1`` reboots the device: the port answers NUL bytes, then
  disappears and re-enumerates.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable

import serial

from ..exceptions import CliCommandError, CliTimeoutError

log = logging.getLogger(__name__)

PROMPT = b"mmwDemo:/>"
DEFAULT_BAUD = 115200
#: writes at or above this baudrate use the char-by-char workaround
HIGH_BAUD_THRESHOLD = 1000000


class RadarCli:
    """Line-oriented client for the mmWave demo CLI on one serial port."""

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUD,
        timeout: float = 3.0,
    ):
        self.port_name = port
        self.timeout = timeout
        self._ser = serial.Serial(
            port,
            baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )

    @classmethod
    def from_serial(cls, ser: serial.Serial, timeout: float = 3.0) -> "RadarCli":
        """Wrap an already-open pyserial port (the caller keeps ownership)."""
        obj = cls.__new__(cls)
        obj.port_name = ser.port
        obj.timeout = timeout
        obj._ser = ser
        return obj

    # -- low level -------------------------------------------------------

    @property
    def serial(self) -> serial.Serial:
        """The underlying pyserial object (advanced use)."""
        return self._ser

    @property
    def baudrate(self) -> int:
        return self._ser.baudrate

    def close(self) -> None:
        if self._ser.is_open:
            self._ser.close()

    def __enter__(self) -> "RadarCli":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def set_baudrate(self, baud: int) -> None:
        """Change the host-side baudrate (device side must already match)."""
        self._ser.baudrate = baud

    def _write_line(self, line: str) -> None:
        if not line.endswith("\n"):
            line += "\n"
        if self._ser.baudrate >= HIGH_BAUD_THRESHOLD:
            # Firmware UART RX drops chars at this rate; pace them out.
            for ch in line:
                time.sleep(0.001)
                self._ser.write(ch.encode())
        else:
            self._ser.write(line.encode())

    def _read_until_prompt(self, timeout: float) -> bytes:
        """Collect response bytes until Done/Error + prompt or timeout."""
        buffer = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = self._ser.read(self._ser.in_waiting or 1)
            if chunk:
                buffer += chunk.replace(b"\x00", b"")
            if PROMPT in buffer and (
                b"Done" in buffer or b"Error" in buffer or b"not recognized" in buffer
            ):
                return buffer
            time.sleep(0.005)
        raise CliTimeoutError(
            f"No CLI answer within {timeout:.1f}s (got {buffer[-200:]!r}). "
            "Is the right firmware flashed and the board in functional mode (SOP_MODE2)?"
        )

    # -- commands --------------------------------------------------------

    def send_command(
        self,
        line: str,
        *,
        wait_done: bool = True,
        timeout: float | None = None,
    ) -> str:
        """Send one CLI line and (by default) wait for its acknowledgement.

        Returns the decoded response text. Raises :class:`CliCommandError`
        if the firmware answered with ``Error``.
        """
        line = line.strip()
        if not line:
            return ""
        log.debug("CLI> %s", line)
        self._ser.reset_input_buffer()
        self._write_line(line)
        if not wait_done:
            return ""
        response = self._read_until_prompt(timeout or self.timeout)
        text = response.decode(errors="replace")
        if b"Error" in response:
            raise CliCommandError(line, text)
        return text

    def send_config(self, config) -> list[str]:
        """Send a whole configuration.

        ``config`` may be a path to a ``.cfg`` file, an iterable of CLI
        lines, or a :class:`openwaves.config.RadarConfig`. Comment (``%``)
        and blank lines are skipped. A ``baudRate <n>`` line switches the
        host port to the new rate right after the command is acknowledged.

        Returns the list of response texts, one per line sent.
        """
        lines = _config_to_lines(config)
        responses: list[str] = []
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("%"):
                continue
            time.sleep(0.03)  # inter-line delay the firmware CLI needs
            parts = line.split()
            if parts[0] == "baudRate" and len(parts) > 1:
                # The firmware re-inits its UART at the new rate as soon as
                # it processes the command — its 'Done' goes out at the NEW
                # baud, so don't wait for it at the old one; just follow.
                new_baud = int(parts[1])
                self.send_command(line, wait_done=False)
                time.sleep(0.1)
                log.info("Switching CLI port to %d baud", new_baud)
                self.set_baudrate(new_baud)
                time.sleep(0.05)
                self._ser.reset_input_buffer()
                responses.append("")
                continue
            is_sensor_start = parts[0] == "sensorStart"
            # sensorStart begins streaming: on single-UART firmware the
            # prompt is followed by binary TLV data, so don't wait for it.
            responses.append(
                self.send_command(line, timeout=10.0 if is_sensor_start else None)
            )
        time.sleep(0.03)
        self._ser.reset_input_buffer()
        return responses

    def sensor_start(self) -> None:
        self.send_command("sensorStart 0 0 0 0", timeout=10.0)

    def sensor_stop(self, timeout: float = 3.0) -> None:
        self.send_command("sensorStop 0", timeout=timeout)
        time.sleep(0.2)

    def warm_reset(self) -> None:
        """Send ``sensorWarmRst 1`` and close the port.

        The device reboots and its USB serial ports re-enumerate; use
        :func:`openwaves.transport.find_radar_ports` again afterwards.
        """
        log.info("Sending warm reset...")
        self._ser.reset_input_buffer()
        self._write_line("sensorWarmRst 1")
        # NUL bytes confirm the reset fired
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            raw = self._ser.read(self._ser.in_waiting or 1)
            if b"\x00" in raw:
                log.info("Reset firing")
                break
            time.sleep(0.01)
        self.close()
        time.sleep(0.5)

    def probe_version(self) -> str:
        """Send ``version`` and return the raw response text ('' on timeout).

        Used to tell firmware variants apart (TI's stock demos answer with a
        platform string containing e.g. ``L684x``).
        """
        try:
            self._ser.reset_input_buffer()
            self._write_line("version")
            time.sleep(0.1)
            deadline = time.monotonic() + 1.0
            buffer = b""
            while time.monotonic() < deadline:
                chunk = self._ser.read(self._ser.in_waiting or 1)
                if chunk:
                    buffer += chunk
                if PROMPT in buffer:
                    break
            return buffer.decode(errors="replace")
        except serial.SerialException:
            return ""


def _config_to_lines(config) -> Iterable[str]:
    if hasattr(config, "to_lines"):  # RadarConfig
        return config.to_lines()
    if isinstance(config, (str, Path)):
        return Path(config).read_text().splitlines()
    return list(config)
