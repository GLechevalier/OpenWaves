"""The ``openwaves`` console entry point.

Subcommands::

    openwaves ports                      list serial ports, mark the radar
    openwaves flash [APPIMAGE]           flash firmware (bundled by default)
    openwaves config CFGFILE             send a configuration
    openwaves stream [--cfg CFG] ...     configure, start and print frames
    openwaves record OUT [--raw] ...     record frames or the raw stream
    openwaves replay IN.bin              parse a raw capture
    openwaves term                       interactive CLI terminal
    openwaves reset                      warm-reset the sensor
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from . import __version__
from .exceptions import OpenWavesError
from .frames import FrameData


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.command is None:
        parser.print_help()
        return 1
    try:
        return args.func(args) or 0
    except OpenWavesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openwaves",
        description="Toolkit for the TI IWRL6432BOOST mmWave radar (OpenWaves).",
    )
    parser.add_argument("--version", action="version", version=f"openwaves {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("ports", help="list serial ports and mark the detected radar")
    p.set_defaults(func=cmd_ports)

    p = sub.add_parser("flash", help="flash an .appimage over the UART bootloader")
    p.add_argument("appimage", nargs="?", default=None,
                   help="image path (default: bundled prebuilt firmware)")
    p.add_argument("--port", help="CLI/User UART port (default: autodetect)")
    p.add_argument("--erase", action="store_true", help="erase storage first")
    p.add_argument("--sram", action="store_true", help="load to SRAM instead of SFLASH")
    p.add_argument("--timeout", type=float, default=30.0, help="bootloader connect timeout (s)")
    p.set_defaults(func=cmd_flash)

    p = sub.add_parser("config", help="send a .cfg configuration (without sensorStart)")
    p.add_argument("cfgfile")
    p.add_argument("--port", help="CLI port (default: autodetect)")
    p.add_argument("--start", action="store_true", help="also send sensorStart")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("stream", help="configure, start and print live frames")
    p.add_argument("--cfg", help=".cfg file to send first (default: none, sensor "
                              "assumed configured)")
    p.add_argument("--count", type=int, default=None, help="stop after N frames")
    p.add_argument("--json", action="store_true", help="print one JSON object per frame")
    p.set_defaults(func=cmd_stream)

    p = sub.add_parser("record", help="record frames (.jsonl) or the raw stream (--raw .bin)")
    p.add_argument("output")
    p.add_argument("--cfg", help=".cfg file to send first")
    p.add_argument("--duration", type=float, default=10.0, help="seconds to record")
    p.add_argument("--raw", action="store_true", help="record raw UART bytes")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("replay", help="parse a raw .bin capture and print frames")
    p.add_argument("input")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("term", help="interactive mmWave CLI terminal")
    p.add_argument("--port", help="CLI port (default: autodetect)")
    p.set_defaults(func=cmd_term)

    p = sub.add_parser("reset", help="send sensorWarmRst and wait for re-enumeration")
    p.set_defaults(func=cmd_reset)

    return parser


# -- commands ------------------------------------------------------------


def cmd_ports(args) -> int:
    from .transport import find_all_radars, list_all_ports

    radars = find_all_radars()
    cli_ports = {r.cli_port for r in radars}
    data_ports = {r.data_port for r in radars}
    print("Serial ports:")
    for p in list_all_ports():
        tag = ""
        if p.device in cli_ports:
            tag = "  <-- radar CLI port"
        elif p.device in data_ports:
            tag = "  <-- radar DATA port"
        print(f"  {p.device:12s} {p.description or '?'}{tag}")
    if radars:
        print("\nDetected radars:")
        for r in radars:
            print(f"  {r}")
    else:
        print("\nNo IWRL6432BOOST (XDS110) detected.")
    return 0


def cmd_flash(args) -> int:
    from .flash import FileId, Storage, flash_firmware

    flash_firmware(
        args.appimage,
        port=args.port,
        storage=Storage.SRAM if args.sram else Storage.SFLASH,
        file_id=FileId.META_IMAGE1,
        erase_first=args.erase,
        connect_timeout=args.timeout,
    )
    return 0


def _open_radar(cfg: str | None):
    from .radar import Radar

    radar = Radar().open()
    if cfg:
        print(f"Sending {cfg} ...")
        radar.configure(cfg)
    return radar


def cmd_config(args) -> int:
    radar = _open_radar(args.cfgfile)
    try:
        if args.start:
            radar.start()
            print("Sensor started.")
            radar._started = False  # leave it running after exit
    finally:
        radar.close()
    print("Configuration sent.")
    return 0


def _frame_summary(frame: FrameData) -> str:
    parts = [f"frame {frame.frame_number}"]
    if frame.points is not None:
        parts.append(f"{frame.num_points} pts")
    if frame.capon_heatmap is not None:
        parts.append(f"heatmap {getattr(frame.capon_heatmap, 'shape', '?')}")
    if frame.tracks:
        parts.append(f"{len(frame.tracks)} tracks")
    if frame.raw_tlvs:
        parts.append(f"raw TLVs {sorted(frame.raw_tlvs)}")
    if frame.errors:
        parts.append(f"ERRORS: {frame.errors}")
    return "  ".join(parts)


def _frame_json(frame: FrameData) -> str:
    obj: dict = {
        "frameNumber": frame.frame_number,
        "t": frame.timestamp,
        "numPoints": frame.num_points,
    }
    if frame.points is not None:
        obj["points"] = frame.points[: frame.num_points].tolist()
    if frame.capon_heatmap is not None:
        obj["caponHeatmap"] = frame.capon_heatmap.ravel().tolist()
    if frame.errors:
        obj["errors"] = frame.errors
    return json.dumps(obj)


def cmd_stream(args) -> int:
    radar = _open_radar(args.cfg)
    try:
        radar.start()
        for frame in radar.frames(count=args.count):
            print(_frame_json(frame) if args.json else _frame_summary(frame))
    finally:
        radar.close()
    return 0


def cmd_record(args) -> int:
    from .io import FrameRecorder, RawUartRecorder
    from .tlv.header import sync_and_read_frame

    radar = _open_radar(args.cfg)
    try:
        radar.start()
        deadline = time.monotonic() + args.duration
        if args.raw:
            stream = radar._data_stream()
            with RawUartRecorder(args.output) as rec:
                while time.monotonic() < deadline:
                    rec.write(sync_and_read_frame(stream))
            print(f"Wrote {rec.bytes_written} bytes to {args.output}")
        else:
            with FrameRecorder(args.output, metadata={"cfg": args.cfg or ""}) as rec:
                while time.monotonic() < deadline:
                    rec.write(radar.read_frame())
            print(f"Wrote {rec.frames_written} frames to {args.output}")
    finally:
        radar.close()
    return 0


def cmd_replay(args) -> int:
    from .io import replay_raw

    count = 0
    for frame in replay_raw(args.input):
        print(_frame_json(frame) if args.json else _frame_summary(frame))
        count += 1
    print(f"({count} frames)", file=sys.stderr)
    return 0


def cmd_term(args) -> int:
    from .control import RadarCli
    from .exceptions import CliCommandError, CliTimeoutError
    from .transport import find_radar_ports

    port = args.port or find_radar_ports().cli_port
    print(f"Connected to {port}. Type CLI commands ('help' for the firmware's "
          "list, Ctrl+C to exit).")
    with RadarCli(port) as cli:
        while True:
            try:
                line = input("mmwDemo:/> ")
            except EOFError:
                break
            if not line.strip():
                continue
            try:
                print(cli.send_command(line), end="")
            except (CliTimeoutError, CliCommandError) as exc:
                print(f"! {exc}")
    return 0


def cmd_reset(args) -> int:
    from .radar import Radar

    radar = Radar().open()
    radar.warm_reset(redetect=True)
    print(f"Device back on {radar.ports}")
    radar.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
