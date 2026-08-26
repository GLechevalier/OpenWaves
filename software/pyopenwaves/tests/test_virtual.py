"""VirtualRadar: synthetic frames through the real encode → parse path."""

import numpy as np
import pytest

from openwaves.exceptions import OpenWavesError
from openwaves.virtual import Target, VirtualRadar


def make_radar(**kwargs):
    scene = [Target(x=0.0, y=2.0, velocity=(1.0, 0.0, 0.0), points_per_frame=10)]
    return VirtualRadar(scene, fps=1000.0, noise_points=0, seed=0, **kwargs)


def test_requires_open_and_start():
    radar = make_radar()
    with pytest.raises(OpenWavesError):
        radar.start()
    with radar:
        with pytest.raises(OpenWavesError):
            radar.read_frame()


def test_frames_parse_through_real_pipeline():
    with make_radar() as radar:
        radar.configure([])
        radar.start()
        frames = list(radar.frames(count=3, realtime=False))
    assert [f.frame_number for f in frames] == [1, 2, 3]
    for f in frames:
        assert f.ok, f.errors
        assert f.num_points == 10
        assert f.points.shape == (10, 7)


def test_target_moves_between_frames():
    with make_radar() as radar:
        radar.start()
        first = radar.read_frame()
        for _ in range(999):
            last = radar.read_frame()  # 1000 frames at 1000 fps = 1 s at 1 m/s
    dx = last.points[:, 0].mean() - first.points[:, 0].mean()
    assert dx == pytest.approx(1.0, abs=0.2)


def test_doppler_matches_radial_velocity():
    # target directly ahead, receding at 1 m/s → doppler ≈ +1
    scene = [Target(x=0.0, y=2.0, velocity=(0.0, 1.0, 0.0), points_per_frame=20)]
    with VirtualRadar(scene, fps=10, noise_points=0, seed=1) as radar:
        radar.start()
        frame = radar.read_frame()
    assert np.abs(frame.points[:, 3].mean() - 1.0) < 0.1


def test_seed_reproducible():
    def run():
        with make_radar() as radar:
            radar.start()
            return radar.read_frame().points

    np.testing.assert_array_equal(run(), run())
