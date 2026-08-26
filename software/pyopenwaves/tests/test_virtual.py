"""VirtualRadar: bench-realistic synthetic frames through the real encode → parse path."""

import numpy as np
import pytest

from openwaves.config import get_profile_cfg, parse_cfg
from openwaves.exceptions import OpenWavesError
from openwaves.virtual import Target, VirtualRadar, office_scene


def make_radar(targets=None, **kwargs):
    if targets is None:
        targets = [Target(x=0.0, y=2.0)]
    kwargs.setdefault("fps", 1000.0)
    kwargs.setdefault("noise_points", 0)
    kwargs.setdefault("seed", 0)
    kwargs.setdefault("p_detect", 1.0)
    kwargs.setdefault("p_extra", 0.0)
    return VirtualRadar(targets, **kwargs)


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
        # one static target appears in both the major and minor lists
        assert f.num_points == 2
        assert f.points.shape == (2, 7)
        assert (f.points[:, 6] == 255).all()  # unassociated, like the bench


def test_static_scene_coordinates_stable_and_doppler_zero():
    with make_radar(office_scene()) as radar:
        radar.start()
        frames = [radar.read_frame() for _ in range(5)]
    first = frames[0].points
    assert first is not None and len(first) == 18  # 9 reflectors x (major+minor)
    for f in frames[1:]:
        np.testing.assert_array_equal(f.points[:, :3], first[:, :3])
        assert (f.points[:, 3] == 0.0).all()  # doppler exactly zero


def test_quantization_matches_bench():
    # real coordinates recorded from the board: quantization must reproduce them
    bench = [
        (1.312, 4.913, 0.656),
        (-0.562, 0.933, -0.141),
        (-3.186, 5.106, -1.593),
    ]
    targets = [Target(x=x, y=y, z=z) for x, y, z in bench]
    with make_radar(targets) as radar:
        radar.start()
        frame = radar.read_frame()
    majors = frame.points[: len(bench), :3]
    np.testing.assert_allclose(majors, np.array(bench), atol=2e-3)


def test_target_moves_between_frames():
    scene = [Target(x=0.0, y=2.0, velocity=(1.0, 0.0, 0.0))]
    with make_radar(scene) as radar:
        radar.start()
        first = radar.read_frame()
        for _ in range(999):
            last = radar.read_frame()  # 1000 frames at 1000 fps = 1 s at 1 m/s
    dx = last.points[:, 0].mean() - first.points[:, 0].mean()
    assert dx == pytest.approx(1.0, abs=0.3)  # bin-quantized positions


def test_doppler_matches_radial_velocity():
    # target directly ahead, receding at 1 m/s → doppler on the 0.19333 grid
    scene = [Target(x=0.0, y=2.0, velocity=(0.0, 1.0, 0.0))]
    with make_radar(scene, fps=10) as radar:
        radar.start()
        f1 = radar.read_frame()
        f2 = radar.read_frame()
    # fast mover: major list only
    assert f1.num_points == 1
    d = f1.points[0, 3]
    assert abs(d - 1.0) < radar.params.doppler_res
    assert f2.points[0, 3] == d  # quantized → identical next frame


def test_major_minor_lists():
    with make_radar() as radar:
        radar.start()
        frame = radar.read_frame()
    noise = frame.points[:, 5]
    snr = frame.points[:, 4]
    assert frame.num_points == 2
    assert 4.0 - 0.1 <= noise[1] - noise[0] <= 6.0 + 0.1
    assert ((snr >= 8.0 - 0.05) & (snr <= 31.25)).all()
    # SNR sits on a 0.25 dB grid (±0.05 for the 0.1 dB wire step)
    assert (np.abs(snr - np.round(snr * 4) / 4) <= 0.051).all()
    # major-only firmware mode drops the minor list
    with make_radar() as radar:
        radar.configure(["sigProcChainCfg 8 16 1 2 8 8 1 0.3"])
        radar.start()
        assert radar.read_frame().num_points == 1


def test_configure_derives_params():
    radar = VirtualRadar([])
    radar.configure(parse_cfg(get_profile_cfg("mpd_tracking_midbw")))
    p = radar.params
    assert p.range_res == pytest.approx(0.183105, abs=1e-4)
    assert p.u_step == pytest.approx(0.25586, abs=1e-4)
    assert p.v_step == pytest.approx(0.12793, abs=1e-4)
    assert p.doppler_res == pytest.approx(0.19333, abs=1e-4)
    assert radar.fps == pytest.approx(10.0)
    # explicit fps overrides the derived one
    assert VirtualRadar([], fps=500.0).fps == 500.0


def test_gating():
    targets = [
        Target(x=0.0, y=9.0),                  # beyond rangeSelCfg max (7.5 m)
        Target(x=0.0, y=0.04),                 # inside min range gate
        Target(x=3.0, y=0.5),                  # azimuth ~80 deg, outside FOV
        Target(x=0.0, y=-2.0),                 # behind the board
    ]
    with make_radar(targets) as radar:
        radar.start()
        frame = radar.read_frame()
    assert frame.num_points == 0


def test_seed_reproducible():
    def run():
        with make_radar(office_scene(), p_detect=0.9, p_extra=0.3) as radar:
            radar.start()
            return radar.read_frame().points

    np.testing.assert_array_equal(run(), run())
