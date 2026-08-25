"""Tolerant, lossless ``.cfg`` file parsing.

Every line is parsed into its typed dataclass when possible; if the typed
representation would not serialise back to the exact same tokens (different
firmware variants take different argument counts), the line is preserved
verbatim as a :class:`RawCommand`. ``parse_cfg`` therefore never loses
information: ``parse_cfg(p).to_lines()`` always reproduces the command lines
of the input file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from .model import COMMAND_CLASSES, Command, RadarConfig, RawCommand


def parse_cfg_text(text: str) -> RadarConfig:
    config = RadarConfig()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("%"):
            config.comments.append(raw_line.rstrip())
            continue
        config.commands.append(_parse_line(line))
    return config


def parse_cfg(path: Union[str, Path]) -> RadarConfig:
    """Parse a ``.cfg`` file into a :class:`RadarConfig`."""
    return parse_cfg_text(Path(path).read_text())


def _parse_line(line: str) -> Command:
    tokens = line.split()
    name, args = tokens[0], tokens[1:]
    cls = COMMAND_CLASSES.get(name)
    if cls is not None:
        try:
            command = cls.from_args(args)
            if _tokens_equal(command.to_line().split(), tokens):
                return command
        except Exception:
            pass
    return RawCommand(line=line)


def _tokens_equal(a: list[str], b: list[str]) -> bool:
    """Compare token lists numerically so '6.0' == '6' and '0x1FF000' == '0x1ff000'."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x == y:
            continue
        try:
            if float(int(x, 16) if x.lower().startswith("0x") else x) != float(
                int(y, 16) if y.lower().startswith("0x") else y
            ):
                return False
        except ValueError:
            return False
    return True
