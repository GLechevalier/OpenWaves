"""Encode → parse round-trip tests (bit-level, no hardware)."""

import numpy as np
import pytest

from openwaves.tlv import defines, encode
from openwaves.tlv.header import sync_and_read_frame
from openwaves.tlv.registry import DEFAULT_REGISTRY


def make_point_frame(n=5, frame_number=42):
    rng = np.random.default_rng(0)
    xyzd = rng.uniform(-5, 5, (n, 4))
    snr = rng.uniform(0, 40, n).round(1)
    noise = rng.uniform(0, 20, n).round(1)
    frame_bytes = encode.encode_frame(
        [
            encode.encode_detected_points(xyzd),
            encode.encode_side_info(snr, noise),
        ],
        frame_number=frame_number,
        num_detected_obj=n,
    )
    return frame_bytes, xyzd, snr, noise


def test_frame_length_is_padded_to_32():
    frame_bytes, *_ = make_point_frame()
    assert len(frame_bytes) % defines.FRAME_PADDING == 0


def test_point_cloud_roundtrip():
    frame_bytes, xyzd, snr, noise = make_point_frame()
    frame = DEFAULT_REGISTRY.parse_frame(frame_bytes)
    assert frame.ok, frame.errors
    assert frame.frame_number == 42
    assert frame.num_points == 5
    np.testing.assert_allclose(frame.points[:5, 0:4], xyzd, rtol=1e-6)
    np.testing.assert_allclose(frame.points[:5, 4], snr, atol=0.051)
    np.testing.assert_allclose(frame.points[:5, 5], noise, atol=0.051)
    # unassociated by default
    assert (frame.points[:5, 6] == defines.TRACK_INDEX_NOISE).all()


def test_capon_heatmap_roundtrip():
    heatmap = np.arange(np.prod(defines.CAPON_HEATMAP_SHAPE), dtype=np.float32).reshape(
        defines.CAPON_HEATMAP_SHAPE
    )
    frame_bytes = encode.encode_frame([encode.encode_capon_heatmap(heatmap)], frame_number=7)
    frame = DEFAULT_REGISTRY.parse_frame(frame_bytes)
    assert frame.ok, frame.errors
    assert frame.capon_heatmap.shape == defines.CAPON_HEATMAP_SHAPE
    np.testing.assert_array_equal(frame.capon_heatmap, heatmap)


def test_nonstandard_heatmap_kept_flat_with_note():
    frame_bytes = encode.encode_frame(
        [encode.encode_capon_heatmap(np.zeros(100, dtype=np.float32))]
    )
    frame = DEFAULT_REGISTRY.parse_frame(frame_bytes)
    assert frame.capon_heatmap.shape == (100,)
    assert frame.errors  # a note, not a crash


def test_ext_stats_roundtrip():
    frame_bytes = encode.encode_frame(
        [encode.encode_ext_stats(1234, 567, (10, 20, 30, 40), (50, 60, 70, 80))]
    )
    frame = DEFAULT_REGISTRY.parse_frame(frame_bytes)
    assert frame.stats.inter_frame_proc_time_us == 1234
    assert frame.stats.power_3v3_mw == 20
    assert frame.stats.temp_dig_c == 80


def test_target_list_roundtrip():
    tracks = [
        {
            "track_id": 3,
            "position": (1.0, 2.0, 0.5),
            "velocity": (0.1, -0.2, 0.0),
            "acceleration": (0.0, 0.0, 0.0),
            "g": 3.5,
            "confidence": 0.9,
        }
    ]
    frame_bytes = encode.encode_frame([encode.encode_target_list(tracks)])
    frame = DEFAULT_REGISTRY.parse_frame(frame_bytes)
    assert len(frame.tracks) == 1
    t = frame.tracks[0]
    assert t.track_id == 3
    np.testing.assert_allclose(t.position, [1.0, 2.0, 0.5])
    assert t.confidence == pytest.approx(0.9)


def test_unknown_tlv_preserved_raw():
    payload = b"\xde\xad\xbe\xef" * 4
    frame_bytes = encode.encode_frame([(999, payload)])
    frame = DEFAULT_REGISTRY.parse_frame(frame_bytes)
    assert frame.raw_tlvs[999] == payload


def test_custom_registered_parser():
    from openwaves.tlv.registry import default_registry

    registry = default_registry()

    def parse_magic(payload, frame):
        frame.extras["magic"] = int.from_bytes(payload[:4], "little")

    registry.register(602, parse_magic, name="magic")
    frame_bytes = encode.encode_frame([(602, (12345).to_bytes(4, "little"))])
    frame = registry.parse_frame(frame_bytes)
    assert frame.extras["magic"] == 12345


def test_sync_scans_past_garbage():
    import io

    frame_bytes, *_ = make_point_frame()
    # garbage containing partial magic-word prefixes
    garbage = b"\x00\x02\x01\x04\xff" * 10 + b"\x02\x01"
    stream = io.BytesIO(garbage + frame_bytes)
    recovered = sync_and_read_frame(stream)
    assert recovered == frame_bytes


def test_truncated_tlv_reported_not_raised():
    frame_bytes, *_ = make_point_frame()
    truncated = frame_bytes[: defines.FRAME_HEADER_SIZE + 4]
    frame = DEFAULT_REGISTRY.parse_frame(truncated)
    assert frame.errors


def test_multi_frame_stream_replay(tmp_path):
    from openwaves.io import replay_raw

    frames = [make_point_frame(n, frame_number=i)[0] for i, n in enumerate([3, 5, 8])]
    path = tmp_path / "capture.bin"
    path.write_bytes(b"junk" + b"".join(frames) + b"tail")
    parsed = list(replay_raw(path))
    assert [f.frame_number for f in parsed] == [0, 1, 2]
    assert [f.num_points for f in parsed] == [3, 5, 8]
