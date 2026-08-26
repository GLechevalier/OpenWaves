"""A hardware-free stand-in for :class:`openwaves.Radar`.

``VirtualRadar`` mirrors the ``Radar`` facade (``configure`` / ``start`` /
``frames`` / context manager) but synthesizes its point clouds from a scene
of :class:`Target` objects instead of a serial port. Every frame is encoded
to real firmware wire bytes (:mod:`openwaves.tlv.encode`) and decoded by the
real TLV parser, so code written against it — and the parser itself — runs
exactly as it would with a board plugged in.

Typical use::

    from openwaves.virtual import Target, VirtualRadar

    scene = [Target(x=0.0, y=3.0, velocity=(0.4, 0.0, 0.0))]
    with VirtualRadar(scene, fps=10) as radar:
        radar.configure([])          # any config is accepted
        radar.start()
        for frame in radar.frames(count=20):
            print(frame.frame_number, frame.num_points)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator, Sequence

import numpy as np

from .exceptions import OpenWavesError
from .frames import FrameData
from .tlv import encode
from .tlv.registry import DEFAULT_REGISTRY, TlvRegistry


@dataclass
class Target:
    """One reflector in the virtual scene.

    Positions in meters (radar at the origin, y pointing away from the
    board), velocity in m/s. ``extent`` is the reflector's rough radius —
    detections scatter around the center by that much. ``rcs`` scales the
    reported SNR the way a bigger/shinier object would.
    """

    x: float = 0.0
    y: float = 2.0
    z: float = 0.0
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    extent: float = 0.15
    rcs: float = 1.0
    points_per_frame: int = 12

    position: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        self.position = np.array([self.x, self.y, self.z], dtype=float)

    def step(self, dt: float) -> None:
        self.position = self.position + np.asarray(self.velocity, dtype=float) * dt


class VirtualRadar:
    """Drop-in replacement for :class:`openwaves.Radar` fed by a scene.

    :param targets: the scene — a sequence of :class:`Target` (mutable: move
        them between frames, append, remove).
    :param fps: frame rate; :meth:`frames` paces itself to it unless
        ``realtime=False``.
    :param noise_points: uniform clutter detections added per frame.
    :param seed: seed the RNG for reproducible runs.
    """

    def __init__(
        self,
        targets: Sequence[Target] | None = None,
        *,
        fps: float = 10.0,
        noise_points: int = 3,
        seed: int | None = None,
        registry: TlvRegistry = DEFAULT_REGISTRY,
    ):
        self.targets = list(targets or [])
        self.fps = fps
        self.noise_points = noise_points
        self.registry = registry
        self._rng = np.random.default_rng(seed)
        self._frame_number = 0
        self._open = False
        self._started = False
        self.config_lines: list[str] = []

    # -- lifecycle (mirrors Radar) ---------------------------------------

    def open(self) -> "VirtualRadar":
        self._open = True
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
        """Accept (and remember) any configuration; nothing to send."""
        if hasattr(config, "to_lines"):
            self.config_lines = config.to_lines()
        elif isinstance(config, str):
            from pathlib import Path

            self.config_lines = Path(config).read_text().splitlines()
        else:
            self.config_lines = list(config)

    def start(self) -> None:
        if not self._open:
            raise OpenWavesError(
                "VirtualRadar is not open — use 'with VirtualRadar(...) as radar:'"
            )
        self._started = True

    def stop(self) -> None:
        self._started = False

    # -- synthesis -------------------------------------------------------

    def _detections(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Scatter points off every target + clutter → (xyzd, snr, noise)."""
        xyzd_rows, snr_rows = [], []
        for t in self.targets:
            n = t.points_per_frame
            pts = t.position + self._rng.normal(0.0, t.extent, (n, 3))
            rng_m = np.linalg.norm(t.position) or 1e-6
            radial = float(np.dot(t.velocity, t.position) / rng_m)
            doppler = radial + self._rng.normal(0.0, 0.03, n)
            # crude radar equation: SNR falls off with range^4
            snr = np.clip(35.0 + 10 * np.log10(t.rcs / max(rng_m, 0.1) ** 4), 5.0, 50.0)
            xyzd_rows.append(np.column_stack([pts, doppler]))
            snr_rows.append(self._rng.normal(snr, 1.5, n))
        n_noise = self._rng.poisson(self.noise_points)
        if n_noise:
            clutter = self._rng.uniform([-4, 0.2, -1.5], [4, 8, 1.5], (n_noise, 3))
            xyzd_rows.append(np.column_stack([clutter, self._rng.normal(0, 0.05, n_noise)]))
            snr_rows.append(self._rng.uniform(5, 12, n_noise))
        if not xyzd_rows:
            return np.empty((0, 4)), np.empty(0), np.empty(0)
        xyzd = np.vstack(xyzd_rows)
        snr = np.concatenate(snr_rows)
        noise = self._rng.uniform(3, 8, len(snr))
        return xyzd, snr, noise

    def read_frame(self) -> FrameData:
        """Advance the scene one step and return the next parsed frame."""
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
        """Yield parsed frames, paced to ``fps`` (or flat out if not realtime)."""
        yielded = 0
        while count is None or yielded < count:
            t0 = time.perf_counter()
            yield self.read_frame()
            yielded += 1
            if realtime:
                time.sleep(max(0.0, 1.0 / self.fps - (time.perf_counter() - t0)))
