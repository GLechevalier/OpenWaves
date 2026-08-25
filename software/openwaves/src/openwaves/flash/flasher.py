"""High-level "flash the board" flow with user guidance."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable

from ..exceptions import FlashError, PortNotFoundError
from ..firmware import get_bundled_appimage
from ..transport import find_radar_ports
from .protocol import BootloaderClient, FileId, Storage

log = logging.getLogger(__name__)

SOP_CHECKLIST = """\
── Flash pre-flight checklist ────────────────────────────────────────────
 The IWRL6432BOOST must boot in *flash mode* for the UART bootloader:

   1. Power the board OFF (unplug USB).
   2. Set the SOP switches to SOP_MODE1 (flash / device-management mode):
        S1.1 OFF   S1.2 OFF
   3. Plug USB back in.

 When prompted below, the flasher waits for the bootloader: if the board is
 already powered, press its RESET button (or re-plug USB) so the ROM sees
 the connection request at boot.
──────────────────────────────────────────────────────────────────────────"""

POST_FLASH_STEPS = """\
── Flash complete ────────────────────────────────────────────────────────
 To run the new firmware:
   1. Power the board OFF (unplug USB).
   2. Set the SOP switches back to SOP_MODE2 (functional mode):
        S1.1 ON    S1.2 OFF
   3. Plug USB back in — the firmware boots and the CLI answers on the
      Application/User UART ('openwaves ports' to find it).
──────────────────────────────────────────────────────────────────────────"""


def flash_firmware(
    appimage: Path | str | None = None,
    *,
    port: str | None = None,
    file_id: FileId = FileId.META_IMAGE1,
    storage: Storage = Storage.SFLASH,
    erase_first: bool = False,
    connect_timeout: float = 30.0,
    progress: Callable[[int, int], None] | None = None,
    quiet: bool = False,
) -> None:
    """Flash an ``.appimage`` over the UART bootloader.

    Args:
        appimage: image path; ``None`` flashes the bundled prebuilt
            material-classification firmware.
        port: CLI (Application/User UART) port; ``None`` autodetects the
            XDS110.
        erase_first: erase the storage before downloading.
        progress: ``progress(bytes_sent, total)`` callback; when ``None`` and
            not ``quiet``, a console progress bar is drawn.
    """
    image = Path(appimage) if appimage is not None else get_bundled_appimage()
    if not image.is_file():
        raise FlashError(f"Firmware image not found: {image}")

    if port is None:
        try:
            port = find_radar_ports().cli_port
        except PortNotFoundError:
            raise FlashError(
                "Could not autodetect the board's CLI port. Pass the port "
                "explicitly (openwaves flash --port COMx) — 'openwaves ports' "
                "lists everything visible."
            )

    def say(text: str) -> None:
        if not quiet:
            print(text)

    if progress is None and not quiet:
        progress = _console_progress

    say(SOP_CHECKLIST)
    say(f"\nImage : {image} ({image.stat().st_size} bytes)")
    say(f"Port  : {port}")
    say(f"Target: {storage.name}/{file_id.name}\n")

    client = BootloaderClient(port)
    try:
        client.connect(
            timeout=connect_timeout,
            on_waiting=lambda: say(
                "Waiting for the bootloader — press RESET or re-plug USB now "
                f"(up to {connect_timeout:.0f}s)..."
            ),
        )
        say("Connected to the ROM bootloader.")
        if erase_first:
            say("Erasing storage (this can take a while)...")
            client.erase_storage(storage)
        client.download_file(
            image, file_id=file_id, storage=storage, progress=progress
        )
        if progress is _console_progress:
            print()
    finally:
        client.close()

    say(POST_FLASH_STEPS)


def _console_progress(sent: int, total: int) -> None:
    width = 40
    filled = int(width * sent / total)
    bar = "=" * filled + ">" + " " * (width - filled)
    sys.stdout.write(f"\r[{bar}] {sent}/{total} bytes")
    sys.stdout.flush()
