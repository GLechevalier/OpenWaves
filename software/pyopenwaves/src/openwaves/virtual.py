"""A hardware-free stand-in for :class:`openwaves.Radar`, calibrated to a
real IWRL6432BOOST.

``VirtualRadar`` mirrors the ``Radar`` facade (``configure`` / ``start`` /
``frames`` / context manager) but synthesizes its point clouds from a scene
of :class:`Target` objects instead of a serial port. Its output is modeled
on a bench session with a real board (TI Presence_Demo firmware,
``Tracking_MidBw.cfg``, 2026-08-26):

* positions are quantized to the radar's polar grid — range bins of
  ``c/2B`` and azimuth/elevation *sine-space* bins of ``λ/(N_fft · d)`` —
  so a static reflector reports **identical coordinates frame after
  frame**, exactly like the real board;
* doppler is exactly ``0.0`` for static targets and snaps to the doppler
  resolution for movers;
* frames carry the major- then minor-motion detection lists (near-duplicate
  points, the minor copy ~4–6 dB noisier), SNR in 0.25 dB steps falling
  with range, noise floors of 63–79 dB, and ``track_index`` 255;
* all radar parameters — frame rate, resolutions, FOV and range gates —
  are derived from the same ``.cfg`` file a real board takes (defaults are
  the Tracking_MidBw values).

Every frame is encoded to firmware wire bytes (:mod:`openwaves.tlv.encode`)
and decoded by the real TLV parser, so code written against it runs
unchanged on hardware. One documented deviation: the virtual radar emits
plain point-cloud TLVs (types 1 + 7) where Presence_Demo emits the
compressed type 301 — the *parsed* frames match, raw captures do not.

Typical use::

    from openwaves.virtual import Target, VirtualRadar, office_scene

    scene = office_scene() + [Target(x=-2.0, y=3.0, velocity=(0.8, 0, 0))]
    with VirtualRadar(scene) as radar:
        radar.configure("cfg/Tracking_MidBw.cfg")   # any real .cfg works
        radar.start()
        for frame in radar.frames(count=20):
            print(frame.frame_number, frame.num_points)
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np

from .config import parse_cfg, parse_cfg_text
from .config.model import (
    AntGeometryCfg,
    AoaFovCfg,
    BaudRate,
    CfarCfg,
    ChirpComnCfg,
    ChirpTimingCfg,
    FrameCfg,
    RadarConfig,
    RangeSelCfg,
    SigProcChainCfg,
)
from .exceptions import OpenWavesError
from .frames import FrameData
from .tlv import encode
from .tlv.registry import DEFAULT_REGISTRY, TlvRegistry
from .transport.ports import RadarPorts

log = logging.getLogger(__name__)

C_LIGHT = 3e8

# --- bench-calibrated output statistics (board S/N RI32, office scene) ----
SNR_REF_DB = 19.5            # SNR at 1 m for rcs=1
SNR_SLOPE_DB_PER_DECADE = 13.5
SNR_MAX_DB = 31.25
SNR_JITTER_DB = 0.75
NOISE_LO, NOISE_HI = 63.0, 73.0          # major-list noise floor (dB)
MINOR_NOISE_OFFSET = (4.0, 6.0)          # minor copy is this much noisier
P_DETECT = 0.97              # per-frame detection probability per target
P_EXTRA = 0.15               # baseline neighbor-bin flicker probability


@dataclass(frozen=True)
class DerivedParams:
    """Radar behavior derived from a configuration (see :func:`derive_params`)."""

    fps: float
    range_res: float
    doppler_res: float
    n_doppler: int
    u_step: float
    v_step: float
    r_min: float
    r_max: float
    az_min: float  # radians
    az_max: float
    el_min: float
    el_max: float
    mot_det_mode: int
    force_minor_zero: bool
    minor_incl_thr: float
    snr_min: float


def derive_params(config: RadarConfig) -> DerivedParams:
    """Derive the virtual radar's behavior from a real configuration.

    Missing (or firmware-variant, unparsed) commands fall back to the
    dataclass defaults in :mod:`openwaves.config.model`, which equal the
    Tracking_MidBw values.
    """
    chirp = config.get(ChirpComnCfg) or ChirpComnCfg()
    timing = config.get(ChirpTimingCfg) or ChirpTimingCfg()
    frame = config.get(FrameCfg) or FrameCfg()
    sig = config.get(SigProcChainCfg) or SigProcChainCfg()
    fov = config.get(AoaFovCfg) or AoaFovCfg()
    rng_sel = config.get(RangeSelCfg) or RangeSelCfg()
    ant = config.get(AntGeometryCfg) or AntGeometryCfg()
    cfar = config.get(CfarCfg) or CfarCfg()

    f_s = 100e6 / chirp.dig_output_samp_rate_decim          # ADC sample rate, Hz
    slope = timing.chirp_rf_freq_slope * 1e12               # Hz/s
    bandwidth = slope * (chirp.num_of_adc_samples / f_s)    # Hz
    range_res = C_LIGHT / (2 * bandwidth)
    # center frequency of the *sampled* band (the ADC-skip term matters)
    f_center = (
        timing.chirp_rf_freq_start * 1e9
        + slope * (timing.chirp_adc_skip_samples / f_s)
        + bandwidth / 2
    )
    lambda_c = C_LIGHT / f_center
    dist_x, dist_y = (list(ant.ant_dist_mm) + [2.418, 2.418])[:2]
    u_step = lambda_c / (sig.azimuth_fft_size * dist_x * 1e-3)
    v_step = lambda_c / (sig.elevation_fft_size * dist_y * 1e-3)
    n_doppler = max(2, frame.num_of_bursts_in_frame)
    doppler_res = lambda_c / (2 * n_doppler * frame.burst_periodicity * 1e-6)

    return DerivedParams(
        fps=1000.0 / frame.frame_periodicity,
        range_res=range_res,
        doppler_res=doppler_res,
        n_doppler=n_doppler,
        u_step=u_step,
        v_step=v_step,
        r_min=rng_sel.min_meters,
        r_max=rng_sel.max_meters,
        az_min=math.radians(fov.min_azimuth_deg),
        az_max=math.radians(fov.max_azimuth_deg),
        el_min=math.radians(fov.min_elevation_deg),
        el_max=math.radians(fov.max_elevation_deg),
        mot_det_mode=sig.mot_det_mode,
        force_minor_zero=bool(sig.force_minor_motion_velocity_to_zero),
        minor_incl_thr=sig.minor_motion_velocity_inclusion_thr,
        snr_min=float(cfar.threshold_scale),
    )


@dataclass
class Target:
    """One reflector in the virtual scene.

    Positions in meters (radar at the origin, y pointing away from the
    board), velocity in m/s. ``extent`` scales how often the reflector
    flickers into an adjacent range bin (a bigger object lights up more
    bins); ``rcs`` scales the reported SNR (``+10·log10(rcs)`` dB).
    ``points_per_frame`` is the number of detections per list (real
    reflectors report one).
    """

    x: float = 0.0
    y: float = 2.0
    z: float = 0.0
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    extent: float = 0.15
    rcs: float = 1.0
    points_per_frame: int = 1

    position: np.ndarray = field(init=False, repr=False)
    _neighbor_sign: int = field(init=False, repr=False)

    def __post_init__(self):
        self.position = np.array([self.x, self.y, self.z], dtype=float)
        # a fixed adjacent range bin, chosen deterministically per target,
        # so flickering extras reappear at identical coordinates
        self._neighbor_sign = 1 if hash((self.x, self.y, self.z)) % 2 == 0 else -1

    def step(self, dt: float) -> None:
        self.position = self.position + np.asarray(self.velocity, dtype=float) * dt


def office_scene() -> list[Target]:
    """The static office measured on the bench (board S/N RI32, 2026-08-26).

    Nine persistent reflectors whose quantized coordinates reproduce the
    real recording exactly.
    """
    coords = [
        (-0.047, 0.150, -0.094),
        (0.094, 0.105, 0.117),
        (-0.562, 0.933, -0.141),
        (-3.186, 5.106, -1.593),
        (-3.279, 5.506, 0.0),
        (0.0, 3.304, 1.968),
        (2.624, 4.405, 0.0),
        (2.951, 1.974, -1.476),
        (1.312, 4.913, 0.656),
    ]
    return [Target(x=x, y=y, z=z) for x, y, z in coords]


class VirtualRadar:
    """Drop-in replacement for :class:`openwaves.Radar` fed by a scene.

    :param targets: the scene — a sequence of :class:`Target` (mutable:
        move them between frames, append, remove). ``None`` → the bench
        :func:`office_scene`; pass ``[]`` for an empty room.
    :param fps: explicit frame rate; ``None`` (default) derives it from the
        configuration (10 fps for the default Tracking_MidBw values).
    :param noise_points: extra roaming clutter detections per frame. The
        real board shows none (the office scene *is* the clutter) — kept
        for experiments, default 0.
    :param p_detect: per-frame detection probability of each target.
    :param p_extra: baseline probability of a target's neighbor-bin flicker
        (scaled by ``Target.extent``).
    :param seed: seed the RNG for reproducible runs.
    """

    def __init__(
        self,
        targets: Sequence[Target] | None = None,
        *,
        fps: float | None = None,
        noise_points: int = 0,
        p_detect: float = P_DETECT,
        p_extra: float = P_EXTRA,
        seed: int | None = None,
        registry: TlvRegistry = DEFAULT_REGISTRY,
    ):
        self.targets = list(targets) if targets is not None else office_scene()
        self._fps_override = fps
        self.noise_points = noise_points
        self.p_detect = p_detect
        self.p_extra = p_extra
        self.registry = registry
        self._rng = np.random.default_rng(seed)
        self._frame_number = 0
        self._open = False
        self._started = False
        self.config = RadarConfig()
        self.params = derive_params(self.config)
        self.config_lines: list[str] = []

    @property
    def fps(self) -> float:
        return self._fps_override if self._fps_override is not None else self.params.fps

    # -- lifecycle (mirrors Radar) ---------------------------------------

    def open(self) -> "VirtualRadar":
        self._open = True
        log.info(
            "Radar ports: %s", RadarPorts("VIRT-CLI", "VIRT-DATA", serial_number="VIRT0")
        )
        log.info("Detected single-port firmware layout")
        return self

    def close(self) -> None:
        self._open = False
        self._started = False

    def __enter__(self) -> "VirtualRadar":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    # -- control ---------------------------------------------------------

    def configure(self, config) -> None:
        """Accept a configuration and derive the radar's behavior from it.

        ``config`` may be a :class:`RadarConfig`, a path to a ``.cfg``
        file, or an iterable of CLI lines — same as the real ``Radar``.
        """
        if isinstance(config, RadarConfig):
            self.config = config
        elif isinstance(config, (str, Path)):
            self.config = parse_cfg(config)
        else:
            self.config = parse_cfg_text("\n".join(config))
        self.config_lines = self.config.to_lines()
        self.params = derive_params(self.config)
        baud = self.config.get(BaudRate)
        if baud is not None:
            log.info("Switching CLI port to %d baud", int(baud.baudrate))

    def start(self) -> None:
        if not self._open:
            raise OpenWavesError(
                "VirtualRadar is not open — use 'with VirtualRadar(...) as radar:'"
            )
        self._started = True

    def stop(self) -> None:
        self._started = False

    # -- synthesis -------------------------------------------------------

    def _quantize(self, position: np.ndarray):
        """Snap a position to the radar's (range, sin-az, sin-el) grid.

        Returns ``(xyz_q, r_q, k_r)`` or ``None`` when the point is
        undetectable (behind the board, outside the range gate or FOV).
        """
        p = self.params
        r = float(np.linalg.norm(position))
        if r <= 0 or position[1] <= 0:
            return None
        u = position[0] / r
        v = position[2] / r
        k_r = round(r / p.range_res)
        u_q = round(u / p.u_step) * p.u_step
        v_q = round(v / p.v_step) * p.v_step
        if u_q * u_q + v_q * v_q >= 1.0:
            return None
        r_q = k_r * p.range_res
        if not (p.r_min <= r_q <= p.r_max):
            return None
        el = math.asin(max(-1.0, min(1.0, v_q)))
        cos_el = math.cos(el)
        az = math.asin(max(-1.0, min(1.0, u_q / cos_el))) if cos_el > 1e-9 else 0.0
        if not (p.az_min <= az <= p.az_max and p.el_min <= el <= p.el_max):
            return None
        xyz = np.array(
            [r_q * u_q, r_q * math.sqrt(max(0.0, 1.0 - u_q * u_q - v_q * v_q)), r_q * v_q]
        )
        return xyz, r_q, k_r

    def _quantize_doppler(self, target: Target, r: float) -> float:
        p = self.params
        v_r = float(np.dot(target.velocity, target.position) / max(r, 1e-9))
        k_d = round(v_r / p.doppler_res)
        k_d = max(-p.n_doppler // 2, min(p.n_doppler // 2 - 1, k_d))
        return 0.0 if k_d == 0 else k_d * p.doppler_res

    def _snr(self, r_q: float, rcs: float) -> float:
        p = self.params
        snr = (
            SNR_REF_DB
            - SNR_SLOPE_DB_PER_DECADE * math.log10(max(r_q, 0.05))
            + 10 * math.log10(max(rcs, 1e-6))
            + self._rng.normal(0.0, SNR_JITTER_DB)
        )
        snr = min(SNR_MAX_DB, max(p.snr_min, snr))
        return round(snr * 4) / 4  # 0.25 dB steps, like the real firmware

    def _detections(self):
        """Synthesize one frame's detection lists → (xyzd, snr, noise)."""
        p = self.params
        major: list[tuple[np.ndarray, float, float, float]] = []  # xyz, d, snr, noise
        minor: list[tuple[np.ndarray, float, float, float]] = []

        for t in self.targets:
            q = self._quantize(t.position)
            if q is None:
                continue
            xyz, r_q, k_r = q
            doppler = self._quantize_doppler(t, r_q)
            noise = self._rng.uniform(NOISE_LO, NOISE_HI)

            copies = [(xyz, r_q)]
            p_extra_eff = min(0.5, self.p_extra * t.extent / 0.15)
            if self._rng.random() < p_extra_eff:
                # the target's fixed neighbor range bin
                r_n = (k_r + t._neighbor_sign) * p.range_res
                if p.r_min <= r_n <= p.r_max and r_q > 0:
                    copies.append((xyz * (r_n / r_q), r_n))

            v_r = abs(
                float(np.dot(t.velocity, t.position))
                / max(float(np.linalg.norm(t.position)), 1e-9)
            )
            in_minor = v_r < p.minor_incl_thr or doppler == 0.0
            for _ in range(t.points_per_frame):
                for xyz_c, r_c in copies:
                    if self._rng.random() >= self.p_detect:
                        continue
                    if p.mot_det_mode in (1, 3):
                        major.append((xyz_c, doppler, self._snr(r_c, t.rcs), noise))
                    if p.mot_det_mode in (2, 3) and in_minor:
                        d_minor = 0.0 if p.force_minor_zero else doppler
                        minor.append(
                            (
                                xyz_c,
                                d_minor,
                                self._snr(r_c, t.rcs),
                                noise + self._rng.uniform(*MINOR_NOISE_OFFSET),
                            )
                        )

        for _ in range(self._rng.poisson(self.noise_points) if self.noise_points else 0):
            q = self._quantize(self._rng.uniform([-4, 0.2, -1.5], [4, 8, 1.5]))
            if q is not None:
                xyz, r_q, _ = q
                major.append(
                    (xyz, 0.0, self._snr(r_q, 0.1), self._rng.uniform(NOISE_LO, NOISE_HI))
                )

        rows = major + minor
        if not rows:
            return np.empty((0, 4)), np.empty(0), np.empty(0)
        xyzd = np.array([[*xyz, d] for xyz, d, _, _ in rows])
        snr = np.array([s for _, _, s, _ in rows])
        noise = np.array([n for _, _, _, n in rows])
        return xyzd, snr, noise

    def read_frame(self) -> FrameData:
        """Advance the scene one frame period and return the parsed frame."""
        if not self._started:
            raise OpenWavesError("Sensor not started — call start() first")
        dt = 1.0 / self.fps
        for t in self.targets:
            t.step(dt)
        xyzd, snr, noise = self._detections()
        self._frame_number += 1
        frame_bytes = encode.encode_frame(
            [
                encode.encode_detected_points(xyzd),
                encode.encode_side_info(snr, noise),
            ],
            frame_number=self._frame_number,
            num_detected_obj=len(xyzd),
        )
        frame = self.registry.parse_frame(frame_bytes)
        frame.timestamp = time.time()
        return frame

    def frames(
        self, *, count: int | None = None, realtime: bool = True
    ) -> Iterator[FrameData]:
        """Yield parsed frames, paced to the frame rate (or flat out)."""
        yielded = 0
        while count is None or yielded < count:
            t0 = time.perf_counter()
            yield self.read_frame()
            yielded += 1
            if realtime:
                time.sleep(max(0.0, 1.0 / self.fps - (time.perf_counter() - t0)))
