"""Port autodetection against mocked pyserial listings."""

from types import SimpleNamespace

import pytest

from openwaves.exceptions import PortNotFoundError
from openwaves.transport import ports as ports_mod


def _port(device, description="", vid=None, pid=None, serial_number=None, location=None):
    return SimpleNamespace(
        device=device,
        description=description,
        vid=vid,
        pid=pid,
        serial_number=serial_number,
        location=location,
    )


def _patch(monkeypatch, port_list):
    monkeypatch.setattr(ports_mod.list_ports, "comports", lambda: port_list)


def test_windows_style_detection(monkeypatch):
    _patch(
        monkeypatch,
        [
            _port("COM3", "Intel(R) Active Management"),
            _port(
                "COM11",
                "XDS110 Class Application/User UART (COM11)",
                vid=0x0451,
                pid=0xBEF3,
                serial_number="L410",
            ),
            _port(
                "COM12",
                "XDS110 Class Auxiliary Data Port (COM12)",
                vid=0x0451,
                pid=0xBEF3,
                serial_number="L410",
            ),
        ],
    )
    r = ports_mod.find_radar_ports()
    assert r.cli_port == "COM11"
    assert r.data_port == "COM12"
    assert r.serial_number == "L410"


def test_linux_style_detection_by_vid_pid(monkeypatch):
    _patch(
        monkeypatch,
        [
            _port("/dev/ttyUSB0", "FT232R USB UART", vid=0x0403, pid=0x6001),
            _port(
                "/dev/ttyACM1",
                "XDS110 (03.00.00.32) Embed with CMSIS-DAP",
                vid=0x0451,
                pid=0xBEF3,
                serial_number="L410",
                location="1-2:1.3",
            ),
            _port(
                "/dev/ttyACM0",
                "XDS110 (03.00.00.32) Embed with CMSIS-DAP",
                vid=0x0451,
                pid=0xBEF3,
                serial_number="L410",
                location="1-2:1.0",
            ),
        ],
    )
    r = ports_mod.find_radar_ports()
    assert r.cli_port == "/dev/ttyACM0"
    assert r.data_port == "/dev/ttyACM1"


def test_two_boards_grouped_by_serial(monkeypatch):
    _patch(
        monkeypatch,
        [
            _port("COM11", "XDS110 Class Application/User UART", 0x0451, 0xBEF3, "A"),
            _port("COM12", "XDS110 Class Auxiliary Data Port", 0x0451, 0xBEF3, "A"),
            _port("COM14", "XDS110 Class Application/User UART", 0x0451, 0xBEF3, "B"),
            _port("COM15", "XDS110 Class Auxiliary Data Port", 0x0451, 0xBEF3, "B"),
        ],
    )
    radars = ports_mod.find_all_radars()
    assert len(radars) == 2
    by_sn = {r.serial_number: r for r in radars}
    assert by_sn["A"].cli_port == "COM11"
    assert by_sn["B"].data_port == "COM15"
    picked = ports_mod.find_radar_ports(serial_number="B")
    assert picked.cli_port == "COM14"


def test_no_ports_raises_with_listing(monkeypatch):
    _patch(monkeypatch, [_port("COM1", "Communications Port")])
    with pytest.raises(PortNotFoundError) as exc:
        ports_mod.find_radar_ports()
    assert "COM1" in str(exc.value)
