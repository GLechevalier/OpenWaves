"""Serial-port discovery for the IWRL6432BOOST (XDS110 debug probe).

The board's micro-USB (XDS110) enumerates two virtual COM ports:

* the **CLI port** ("XDS110 Class Application/User UART") — mmWave CLI at
  115200 baud (raised by the ``baudRate`` config command), and
* the **data port** ("XDS110 Class Auxiliary Data Port") — TLV stream for
  firmware that uses the double-port layout (e.g. TI's Motion and Presence
  Detection demo).

On Windows the descriptions above are reported verbatim. On Linux/macOS the
CDC-ACM driver may not expose them, so we fall back to matching the XDS110
USB VID:PID (0451:bef3) and ordering the two interfaces: the lower interface
(first device) is the CLI port, the higher is the data port.
"""

from __future__ import annotations

from dataclasses import dataclass

from serial.tools import list_ports

from ..exceptions import PortNotFoundError

XDS110_VID = 0x0451
XDS110_PID = 0xBEF3

CLI_PORT_DESCRIPTION = "XDS110 Class Application/User UART"
DATA_PORT_DESCRIPTION = "XDS110 Class Auxiliary Data Port"


@dataclass(frozen=True)
class RadarPorts:
    """A detected CLI/data port pair belonging to one board."""

    cli_port: str
    data_port: str
    serial_number: str | None = None
    description: str = ""

    def __str__(self) -> str:
        sn = f" (S/N {self.serial_number})" if self.serial_number else ""
        return f"CLI={self.cli_port} DATA={self.data_port}{sn}"


def list_all_ports():
    """Return every serial port pyserial can see (for diagnostics)."""
    return sorted(list_ports.comports(), key=lambda p: p.device)


def find_all_radars() -> list[RadarPorts]:
    """Find every connected XDS110 CLI/data port pair.

    Ports are grouped by USB serial number so several boards can be told
    apart. Within a group the CLI port is identified by its description
    when available, otherwise by USB interface/device ordering.
    """
    candidates = [
        p
        for p in list_all_ports()
        if (p.vid == XDS110_VID and p.pid == XDS110_PID)
        or CLI_PORT_DESCRIPTION in (p.description or "")
        or DATA_PORT_DESCRIPTION in (p.description or "")
    ]
    if not candidates:
        return []

    groups: dict[str, list] = {}
    for p in candidates:
        groups.setdefault(p.serial_number or "?", []).append(p)

    radars: list[RadarPorts] = []
    for serial_number, ports in sorted(groups.items()):
        cli = next((p for p in ports if CLI_PORT_DESCRIPTION in (p.description or "")), None)
        data = next((p for p in ports if DATA_PORT_DESCRIPTION in (p.description or "")), None)
        if cli is None or data is None:
            # Descriptions unavailable (typical on Linux): order by location
            # then device name; first interface = CLI, second = data.
            ordered = sorted(ports, key=lambda p: (p.location or "", p.device))
            if len(ordered) < 2:
                continue
            cli = cli or ordered[0]
            data = data or ordered[1]
        radars.append(
            RadarPorts(
                cli_port=cli.device,
                data_port=data.device,
                serial_number=None if serial_number == "?" else serial_number,
                description=cli.description or "",
            )
        )
    return radars


def find_radar_ports(*, serial_number: str | None = None) -> RadarPorts:
    """Autodetect the radar's CLI/data port pair.

    Args:
        serial_number: pick a specific board when several are connected.

    Raises:
        PortNotFoundError: no (matching) board found; the message lists every
            visible port to make cabling/driver problems obvious.
    """
    radars = find_all_radars()
    if serial_number is not None:
        radars = [r for r in radars if r.serial_number == serial_number]
    if radars:
        return radars[0]

    seen = "\n".join(
        f"  {p.device}: {p.description or '?'}"
        + (f" [VID:PID {p.vid:04x}:{p.pid:04x}]" if p.vid else "")
        for p in list_all_ports()
    ) or "  (no serial ports visible)"
    hint = (
        "Is the board plugged in via the XDS110 micro-USB port?"
        if serial_number is None
        else f"No board with serial number {serial_number!r} found."
    )
    raise PortNotFoundError(f"No IWRL6432BOOST (XDS110) found. {hint}\nVisible ports:\n{seen}")
