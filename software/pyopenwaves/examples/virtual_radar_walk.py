"""Quick-try example: a person walks past a virtual radar. No hardware.

The VirtualRadar synthesizes point clouds, encodes them to real firmware
wire bytes and runs them through the same TLV parser a live board feeds —
so everything you write here works unchanged on real hardware (swap
VirtualRadar for openwaves.Radar).

Run it:            python examples/virtual_radar_walk.py
With a 3D viewer:  python examples/virtual_radar_walk.py --rerun

Then make it yours: change the scene, add targets, detect when the walker
crosses the boresight, estimate their speed from doppler...
"""

import argparse

import numpy as np

from openwaves.virtual import Target, VirtualRadar


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rerun", action="store_true", help="visualize in the Rerun viewer")
    parser.add_argument("--frames", type=int, default=60)
    args = parser.parse_args()

    rr = None
    if args.rerun:
        import rerun as rr  # pip install -e software/pyopenwaves[viz]

        rr.init("virtual_radar_walk", spawn=True)
        rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)

    scene = [
        Target(x=-2.0, y=3.0, z=0.0, velocity=(0.8, 0.0, 0.0)),   # person walking left→right
        Target(x=1.5, y=1.2, z=-0.3, extent=0.4, rcs=8.0,          # parked metal cabinet
               velocity=(0.0, 0.0, 0.0), points_per_frame=6),
    ]

    with VirtualRadar(scene, fps=10, seed=42) as radar:
        radar.configure([])   # a VirtualRadar accepts any config
        radar.start()
        for frame in radar.frames(count=args.frames):
            pts = frame.points  # (N, 7): x, y, z, doppler, snr, noise, track_index
            moving = pts[np.abs(pts[:, 3]) > 0.2]
            if len(moving):
                centroid = moving[:, :3].mean(axis=0)
                azimuth = np.degrees(np.arctan2(centroid[0], centroid[1]))
                print(f"frame {frame.frame_number:3d}: {frame.num_points:2d} points | "
                      f"mover at {np.linalg.norm(centroid):.2f} m, "
                      f"azimuth {azimuth:+6.1f}°, doppler {moving[:, 3].mean():+.2f} m/s")
            else:
                print(f"frame {frame.frame_number:3d}: {frame.num_points:2d} points | static scene")
            if rr is not None:
                rr.set_time("frame", sequence=frame.frame_number)
                rr.log("world/points", rr.Points3D(
                    positions=pts[:, :3],
                    radii=0.03,
                    colors=np.where(np.abs(pts[:, 3:4]) > 0.2, [255, 80, 80], [120, 160, 255]),
                ))


if __name__ == "__main__":
    main()
