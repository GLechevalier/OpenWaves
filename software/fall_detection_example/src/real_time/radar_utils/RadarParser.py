"""Serial glue for the fall-detection examples — now a thin shim over the
``openwaves`` package (``pip install -e software/pyopenwaves``).

Historically this file imported TI's radar_toolbox parser from a hard-coded
``C:\\ti\\...`` install; everything it needs now lives in-repo. The public
interface (``detect_and_open_COM_ports``, ``sendConfig``,
``read_raw_frame_bytes`` returning a TI-style outputDict, ``sensor_stop``,
``warm_reset_and_wait``, ``redetect_ports``, and the ``cliCom``/``dataCom``/
``parserType`` attributes) is unchanged, so existing scripts keep working.

New code should use :class:`openwaves.Radar` directly.
"""

import os
import time

import serial

from openwaves.compat import frame_to_output_dict
from openwaves.control.cli import RadarCli
from openwaves.tlv.header import sync_and_read_frame
from openwaves.tlv.registry import DEFAULT_REGISTRY
from openwaves.transport import find_radar_ports


class RadarParser:
    guii = {
        "alreadyStarted": "False",
        "cfg_sdk3": "Tracking_MidBw.cfg",
        "cfg_sdk5": "Tracking_MidBw.cfg",
        "cfg_sdk6": "Tracking_MidBw.cfg",
    }

    def __init__(self):
        self.detect_and_open_COM_ports()

    # --- Detect and open COM ports ---
    def detect_and_open_COM_ports(self):
        ports = find_radar_ports()
        self.cliCom = serial.Serial(
            ports.cli_port,
            115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.6,
        )
        self._open_data_port(ports.data_port)
        print(f"Detected: parserType={self.parserType}")
        return self.parserType, self.cliCom, self.dataCom

    def _open_data_port(self, data_port):
        """Probe the firmware ('version') to pick the data port layout.

        Bench-verified: IWRL6432 demos (in-repo 'Parking_Demo' image and
        TI's stock 'Presence_Demo', platform XWRL6432) stream TLVs on the
        CLI UART; only older-generation demos (L684x / xWR18xx/16xx/14xx)
        stream on the auxiliary data port.
        """
        response = RadarCli.from_serial(self.cliCom).probe_version()
        if "mmwdemo" not in response.lower():
            # A previous session's 'baudRate' may have left the CLI UART at
            # a high rate — probe those before giving up.
            for baud in (1250000, 921600):
                self.cliCom.baudrate = baud
                response = RadarCli.from_serial(self.cliCom).probe_version()
                if "mmwdemo" in response.lower():
                    print(f"CLI answered at {baud} baud (left over from a previous run)")
                    break
            else:
                self.cliCom.baudrate = 115200
                response = ""
        response = response.lower()
        if "l684x" in response:
            self.parserType = "DoubleCOMPort6844"
            self.dataCom = serial.Serial(data_port, 1250000, timeout=0.6)
        elif any(tag in response for tag in ("wr18", "wr16", "wr14")):
            self.parserType = "DoubleCOMPort6844"
            self.dataCom = serial.Serial(data_port, 921600, timeout=0.6)
        else:
            # IWRL6432 images: data streams on the CLI port
            self.parserType = "SingleCOMPort"
            self.dataCom = self.cliCom

    # --- Send config ---
    def sendConfig(self, cfg_path=None):
        if cfg_path is None:
            cfg_path = os.path.join("cfg", self.guii["cfg_sdk3"])
        RadarCli.from_serial(self.cliCom).send_config(cfg_path)
        print("Config sent. Starting frame capture...")

    def read_raw_frame_bytes(self):
        stream = self.dataCom if self.parserType != "SingleCOMPort" else self.cliCom
        frame_bytes = sync_and_read_frame(stream)
        frame = DEFAULT_REGISTRY.parse_frame(frame_bytes)
        return frame_to_output_dict(frame)

    def sensor_stop(self, timeout=3.0):
        """Send sensorStop and wait for Done confirmation."""
        RadarCli.from_serial(self.cliCom).sensor_stop(timeout=timeout)
        print("Sensor stopped")
        return True

    def warm_reset_and_wait(self):
        print("Sending warm reset...")
        RadarCli.from_serial(self.cliCom).warm_reset()  # closes cliCom
        if self.dataCom and self.dataCom is not self.cliCom:
            self.dataCom.close()
        time.sleep(0.5)
        print("  Ports closed, letting device boot...")

    def redetect_ports(self):
        """Re-run port detection after warm reset — mirrors first boot."""
        print("  Re-detecting COM ports...")
        parserType, cliCom, dataCom = self.detect_and_open_COM_ports()
        print(f"  Redetected: parserType={parserType}")
        return parserType, cliCom, dataCom
