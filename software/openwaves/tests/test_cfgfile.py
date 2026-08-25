"""Config file parsing: lossless round-trip on every committed .cfg."""

from pathlib import Path

import pytest

from openwaves.config import (
    BaudRate,
    FrameCfg,
    GuiMonitor,
    RadarConfig,
    RawCommand,
    SensorStart,
    parse_cfg,
    parse_cfg_text,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CFG_DIR = REPO_ROOT / "software" / "fall_detection_example" / "cfg"
PROFILE_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "openwaves" / "config" / "profiles"
)

ALL_CFGS = sorted(CFG_DIR.glob("*.cfg")) + sorted(PROFILE_DIR.glob("*.cfg"))


def _command_tokens(path: Path) -> list[list[str]]:
    tokens = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("%"):
            tokens.append(line.split())
    return tokens


@pytest.mark.parametrize("cfg_path", ALL_CFGS, ids=lambda p: p.name)
def test_cfg_roundtrip_lossless(cfg_path):
    config = parse_cfg(cfg_path)
    original = _command_tokens(cfg_path)
    reserialized = [line.split() for line in config.to_lines()]
    assert len(original) == len(reserialized)
    for orig, new in zip(original, reserialized):
        assert orig[0] == new[0]
        assert len(orig) == len(new), f"{orig} vs {new}"
        for a, b in zip(orig[1:], new[1:]):
            try:
                base_a = int(a, 16) if a.lower().startswith("0x") else float(a)
                base_b = int(b, 16) if b.lower().startswith("0x") else float(b)
                assert base_a == base_b, f"{orig} vs {new}"
            except ValueError:
                assert a == b


def test_typed_access():
    config = parse_cfg(CFG_DIR / "Tracking_MidBw.cfg")
    assert config.baudrate == 1250000
    frame_cfg = config.get(FrameCfg)
    assert frame_cfg is not None
    assert frame_cfg.frame_periodicity == 100
    assert config.get(SensorStart) is not None
    assert "trackingCfg" in config.command_names()  # preserved as RawCommand


def test_unknown_command_is_raw():
    config = parse_cfg_text("sensorStop 0\nfrobnicate 1 2 3\n")
    assert isinstance(config.commands[1], RawCommand)
    assert config.commands[1].to_line() == "frobnicate 1 2 3"


def test_programmatic_config_builds_lines():
    config = RadarConfig(
        commands=[
            GuiMonitor(point_cloud=2, tracker_info=1),
            BaudRate(baudrate=921600),
            SensorStart(),
        ]
    )
    lines = config.to_lines()
    assert lines[0] == "guiMonitor 2 0 0 0 0 0 0 0 1 0 0"
    assert lines[1] == "baudRate 921600"
    assert lines[2] == "sensorStart 0 0 0 0"
    assert config.baudrate == 921600
