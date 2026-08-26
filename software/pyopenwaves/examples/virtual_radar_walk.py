"""Quick-try example: a person walks through a virtual office. No hardware.

The VirtualRadar mimics a real plugged-in IWRL6432BOOST: the startup lines,
the frame format, and the data itself (grid-quantized positions, exact-zero
doppler on static reflectors, major+minor detection lists, bench-calibrated
SNR/noise) match what `openwaves stream` shows with a board on USB. The
default scene is a real office measured on the bench, plus a walking
person. Frames go through the same TLV parser a live board feeds, so
everything you write here works unchanged on hardware (swap VirtualRadar
for openwaves.Radar).

Run it:            python examples/virtual_radar_walk.py
With a 3D viewer:  python examples/virtual_radar_walk.py --rerun
JSON per frame:    python examples/virtual_radar_walk.py --json

Then make it yours: change the scene, add targets, detect when the walker
crosses the boresight, estimate their speed from doppler...
"""

import argparse
import logging

import numpy as np

from openwaves.cli import _frame_json, _frame_summary
from openwaves.config import get_profile_cfg
from openwaves.virtual import Target, VirtualRadar, office_scene


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rerun", action="store_true", help="visualize in the Rerun viewer")
    parser.add_argument("--json", action="store_true", help="print one JSON object per frame")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--cfg", default=str(get_profile_cfg("mpd_tracking_midbw")),
                        help="radar configuration to derive behavior from")
    args = parser.parse_args()

    # same log format as a real `openwaves stream` session
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    rr = None
    if args.rerun:
        import rerun as rr  # pip install -e software/pyopenwaves[viz]

        rr.init("virtual_radar_walk", spawn=True)
        rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)

    scene = office_scene() + [
        Target(x=-2.0, y=3.0, z=0.0, velocity=(0.8, 0.0, 0.0)),  # person walking left→right
    ]

    with VirtualRadar(scene, seed=42) as radar:
        print(f"Sending {args.cfg} ...")
        radar.configure(args.cfg)
        radar.start()
        for frame in radar.frames(count=args.frames):
            pts = frame.points if frame.points is not None else np.empty((0, 7))
            if args.json:
                print(_frame_json(frame))
            else:
                line = _frame_summary(frame)
                movers = pts[pts[:, 3] != 0.0]
                if len(movers):
                    centroid = movers[:, :3].mean(axis=0)
                    azimuth = np.degrees(np.arctan2(centroid[0], centroid[1]))
                    line += (f"  | mover at {np.linalg.norm(centroid):.2f} m, "
                             f"azimuth {azimuth:+6.1f} deg, doppler {movers[:, 3].mean():+.2f} m/s")
                print(line)
            if rr is not None:
                rr.set_time("frame", sequence=frame.frame_number)
                rr.log("world/points", rr.Points3D(
                    positions=pts[:, :3],
                    radii=0.03,
                    colors=np.where(pts[:, 3:4] != 0.0, [255, 80, 80], [120, 160, 255]),
                ))


if __name__ == "__main__":
    main()
