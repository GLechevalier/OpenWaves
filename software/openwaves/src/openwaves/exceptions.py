"""Exception hierarchy for the openwaves package."""


class OpenWavesError(Exception):
    """Base class for all openwaves errors."""


class PortNotFoundError(OpenWavesError):
    """No radar (XDS110) serial ports could be found."""


class CliTimeoutError(OpenWavesError):
    """The radar CLI did not answer a command in time."""


class CliCommandError(OpenWavesError):
    """The radar CLI answered a command with an error."""

    def __init__(self, command: str, response: str):
        self.command = command
        self.response = response
        super().__init__(f"Command {command!r} failed: {response.strip()!r}")


class FrameSyncError(OpenWavesError):
    """Could not find the frame magic word in the data stream."""


class FlashError(OpenWavesError):
    """The UART bootloader refused an operation.

    ``code`` holds the 64-bit status word returned by GET_LAST_STATUS when
    available (0 means the device sent a NACK but no status could be read).
    """

    def __init__(self, message: str, code: int | None = None):
        self.code = code
        if code is not None:
            message = f"{message} (bootloader status 0x{code:016x})"
        super().__init__(message)
