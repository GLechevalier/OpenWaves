"""Hardware-in-the-loop smoke test.

Skipped unless a board is plugged in AND OPENWAVES_HIL=1 is set:

    OPENWAVES_HIL=1 pytest software/openwaves/tests/hil -v

Exercises: port detection -> configure -> start -> 10 monotonic frames ->
stop -> warm reset -> redetect.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("OPENWAVES_HIL") != "1",
    reason="hardware-in-loop test (set OPENWAVES_HIL=1 with a board plugged in)",
)


def test_stream_smoke():
    from openwaves import Radar
    from openwaves.config import get_profile_cfg

    cfg = os.environ.get("OPENWAVES_HIL_CFG") or str(get_profile_cfg("mpd_tracking_midbw"))

    with Radar() as radar:
        radar.configure(cfg)
        radar.start()
        numbers = [frame.frame_number for frame in radar.frames(count=10)]
        assert len(numbers) == 10
        assert all(b >= a for a, b in zip(numbers, numbers[1:])), numbers
        radar.stop()
        radar.warm_reset(redetect=True)
        assert radar.ports is not None
