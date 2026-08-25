"""Typed models for mmWave CLI configuration commands.

Each dataclass mirrors one CLI command's argument signature (from the
firmware's command table) and serialises back to the exact CLI line via
``to_line()``. Commands the package does not model — or lines with a
non-standard argument count — are preserved verbatim as ``RawCommand`` so
any ``.cfg`` file round-trips losslessly.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import ClassVar, Iterable, Union


def _fmt(value) -> str:
    """Format numbers the way .cfg files write them."""
    if isinstance(value, float):
        text = f"{value:.6f}".rstrip("0").rstrip(".")
        return text if text not in ("", "-") else "0"
    return str(value)


@dataclass
class Command:
    """Base class: serialises dataclass fields to '<name> <arg> <arg> ...'."""

    NAME: ClassVar[str] = ""

    def to_line(self) -> str:
        args = []
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, (list, tuple)):
                args.extend(_fmt(v) for v in value)
            else:
                args.append(_fmt(value))
        return " ".join([self.NAME, *args]).strip()

    @classmethod
    def from_args(cls, args: list[str]) -> "Command":
        converted = []
        i = 0
        for f in fields(cls):  # declaration order, ClassVars excluded
            hint = f.type
            if "list" in str(hint):
                converted.append([_num(a) for a in args[i:]])
                i = len(args)
            else:
                converted.append(_num(args[i]) if "float" in str(hint) or "int" in str(hint) else args[i])
                i += 1
        return cls(*converted)


def _num(text: str):
    try:
        if text.lower().startswith("0x"):
            return int(text, 16)
        return int(text)
    except ValueError:
        return float(text)


@dataclass
class RawCommand(Command):
    """A CLI line kept verbatim (unmodelled or non-standard)."""

    line: str = ""

    def to_line(self) -> str:
        return self.line

    @property
    def name(self) -> str:
        return self.line.split()[0] if self.line.split() else ""


@dataclass
class SensorStop(Command):
    NAME: ClassVar[str] = "sensorStop"
    frame_stop_mode: int = 0


@dataclass
class ChannelCfg(Command):
    NAME: ClassVar[str] = "channelCfg"
    rx_ch_ctrl_bitmask: int = 7
    tx_ch_ctrl_bitmask: int = 3
    misc_ctrl: int = 0


@dataclass
class ChirpComnCfg(Command):
    NAME: ClassVar[str] = "chirpComnCfg"
    dig_output_samp_rate_decim: int = 16
    dig_output_bits_sel: int = 0
    dfe_fir_sel: int = 0
    num_of_adc_samples: int = 128
    chirp_tx_mimo_pat_sel: int = 4
    chirp_ramp_end_time: float = 28.0
    chirp_rx_hpf_sel: int = 3


@dataclass
class ChirpTimingCfg(Command):
    NAME: ClassVar[str] = "chirpTimingCfg"
    chirp_idle_time: float = 6.0
    chirp_adc_skip_samples: int = 32
    chirp_tx_start_time: float = 0.0
    chirp_rf_freq_slope: float = 40.0
    chirp_rf_freq_start: float = 60.0


@dataclass
class FrameCfg(Command):
    NAME: ClassVar[str] = "frameCfg"
    num_of_chirps_in_burst: int = 2
    num_of_chirps_accum: int = 0
    burst_periodicity: float = 200.0
    num_of_bursts_in_frame: int = 64
    frame_periodicity: float = 100.0
    num_of_frames: int = 0


@dataclass
class GuiMonitor(Command):
    NAME: ClassVar[str] = "guiMonitor"
    point_cloud: int = 0
    range_profile: int = 0
    noise_profile: int = 0
    range_azimuth_heat_map: int = 0
    range_doppler_heat_map: int = 0
    stats_info: int = 0
    presence_info: int = 0
    adc_samples: int = 0
    tracker_info: int = 0
    micro_doppler_info: int = 0
    classifier_info: int = 0


@dataclass
class SigProcChainCfg(Command):
    NAME: ClassVar[str] = "sigProcChainCfg"
    azimuth_fft_size: int = 8
    elevation_fft_size: int = 16
    mot_det_mode: int = 3
    coherent_doppler: int = 2
    num_frm_per_minor_mot_proc: int = 8
    num_minor_motion_chirps_per_frame: int = 8
    force_minor_motion_velocity_to_zero: int = 1
    minor_motion_velocity_inclusion_thr: float = 0.3


@dataclass
class CfarCfg(Command):
    NAME: ClassVar[str] = "cfarCfg"
    average_mode: int = 2
    win_len: int = 8
    guard_len: int = 4
    noise_div: int = 3
    cyclic_mode: int = 0
    threshold_scale: float = 8.0
    peak_grouping_en: int = 0
    # Some demos take extra args after peakGroupingEn; kept as a tail list.
    extra: list = field(default_factory=list)


@dataclass
class AoaFovCfg(Command):
    NAME: ClassVar[str] = "aoaFovCfg"
    min_azimuth_deg: float = -60.0
    max_azimuth_deg: float = 60.0
    min_elevation_deg: float = -40.0
    max_elevation_deg: float = 40.0


@dataclass
class RangeSelCfg(Command):
    NAME: ClassVar[str] = "rangeSelCfg"
    min_meters: float = 0.1
    max_meters: float = 7.5


@dataclass
class ClutterRemoval(Command):
    NAME: ClassVar[str] = "clutterRemoval"
    enabled: int = 1


@dataclass
class SensorPosition(Command):
    NAME: ClassVar[str] = "sensorPosition"
    x_offset: float = 0.0
    y_offset: float = 0.0
    z_offset: float = 1.2
    azimuth_tilt: float = 0.0
    elevation_tilt: float = 0.0


@dataclass
class LowPowerCfg(Command):
    NAME: ClassVar[str] = "lowPowerCfg"
    enabled: int = 0


@dataclass
class FactoryCalibCfg(Command):
    NAME: ClassVar[str] = "factoryCalibCfg"
    save_enable: int = 1
    restore_enable: int = 0
    rx_gain: float = 40.0
    backoff0: float = 0.0
    flash_offset: int = 0x1FF000

    def to_line(self) -> str:
        return (
            f"{self.NAME} {_fmt(self.save_enable)} {_fmt(self.restore_enable)} "
            f"{_fmt(self.rx_gain)} {_fmt(self.backoff0)} 0x{self.flash_offset:x}"
        )


@dataclass
class BaudRate(Command):
    NAME: ClassVar[str] = "baudRate"
    baudrate: int = 1250000


@dataclass
class AntGeometryCfg(Command):
    NAME: ClassVar[str] = "antGeometryCfg"
    rows_cols: list = field(default_factory=lambda: [0, 0, 1, 1, 0, 2, 0, 1, 1, 2, 0, 3])
    # antDistX / antDistY in mm; the default reflects the OpenWaves antenna.
    ant_dist_mm: list = field(default_factory=lambda: [2.418, 2.418])

    @classmethod
    def from_args(cls, args: list[str]) -> "AntGeometryCfg":
        values = [_num(a) for a in args]
        return cls(rows_cols=values[:-2], ant_dist_mm=values[-2:])


@dataclass
class SensorStart(Command):
    NAME: ClassVar[str] = "sensorStart"
    frame_trig_mode: int = 0
    loop_back_en: int = 0
    frame_liv_mon_en: int = 0
    frame_trig_timer_val: int = 0


#: command name -> dataclass, for the .cfg parser
COMMAND_CLASSES: dict[str, type[Command]] = {
    cls.NAME: cls
    for cls in (
        SensorStop,
        ChannelCfg,
        ChirpComnCfg,
        ChirpTimingCfg,
        FrameCfg,
        GuiMonitor,
        SigProcChainCfg,
        CfarCfg,
        AoaFovCfg,
        RangeSelCfg,
        ClutterRemoval,
        SensorPosition,
        LowPowerCfg,
        FactoryCalibCfg,
        BaudRate,
        AntGeometryCfg,
        SensorStart,
    )
}


@dataclass
class RadarConfig:
    """An ordered radar configuration: a list of commands plus comments.

    ``commands`` preserves file order. Serialise with :meth:`to_lines`,
    look commands up with :meth:`get`.
    """

    commands: list[Command] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)

    def to_lines(self) -> list[str]:
        return [c.to_line() for c in self.commands]

    def to_text(self) -> str:
        return "\n".join([*self.comments, *self.to_lines()]) + "\n"

    def save(self, path: Union[str, Path]) -> None:
        Path(path).write_text(self.to_text())

    def get(self, command_cls: type[Command]):
        """First command of the given class, or None."""
        for c in self.commands:
            if isinstance(c, command_cls):
                return c
        return None

    def command_names(self) -> list[str]:
        return [
            c.name if isinstance(c, RawCommand) else c.NAME for c in self.commands
        ]

    @property
    def baudrate(self) -> int | None:
        cmd = self.get(BaudRate)
        return int(cmd.baudrate) if cmd else None
