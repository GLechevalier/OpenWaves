import sys
import os
import time


sys.path.append(r'C:\ti\radar_toolbox_3_20_00_04\tools\visualizers\Applications_Visualizer\common')
sys.path.append(r'C:\ti\radar_toolbox_3_20_00_04\tools\mmwave_data_recorder\src')

from gui_parser import UARTParser
from parser_lib import get_coms_ports, readAndParseUartDoubleCOMPort, sendCfg
import parseFrame

# Patch parseStandardFrame to enable point cloud output
_original_parse = parseFrame.parseStandardFrame
def patched_parse(frameData, pointcloud_output=False):
    return _original_parse(frameData, pointcloud_output=True)
parseFrame.parseStandardFrame = patched_parse

class RadarParser:
    guii = {
        "alreadyStarted": "False",
        "cfg_sdk3": "Tracking_MidBw.cfg",       
        "cfg_sdk5": "Tracking_MidBw.cfg",   
        "cfg_sdk6": "Tracking_MidBw.cfg",  
    }
    def __init__(self):
        self.detect_and_open_COM_ports()
        return
    
    # --- Detect and open COM ports ---
    def detect_and_open_COM_ports(self):
        parserType, cliCom, dataCom = get_coms_ports(self.guii, bypass_ack=False)
        print(f"Detected: parserType={parserType}")
        self.parserType = parserType
        self.cliCom = cliCom
        self.dataCom = dataCom
        return parserType, cliCom, dataCom

    # --- Send config ---
    def sendConfig(self, cfg_path=None):
        if cfg_path is None:
            cfg_path = os.path.join("cfg", self.guii["cfg_sdk3"])  # Adjust to match your parserType
        with open(cfg_path, "r") as f:
            cfg = f.readlines()
        sendCfg(self.cliCom, cfg, self.guii)
        print("Config sent. Starting frame capture...")
        return 

    def read_raw_frame_bytes(self):
        # Read raw frame bytes
        if self.parserType in ["DoubleCOMPort", "DoubleCOMPort6844"]:
            frameData = readAndParseUartDoubleCOMPort(self.dataCom, self.parserType)
        elif self.parserType == "SingleCOMPort":
            frameData = readAndParseUartDoubleCOMPort(self.cliCom, self.parserType)

        # Parse frame (patched to enable pointcloud)
        outputDict = parseFrame.parseStandardFrame(frameData)

        return outputDict
    
    def sensor_stop(self, timeout=3.0):
        """Send sensorStop and wait for Done confirmation."""
        self.cliCom.reset_input_buffer()
        self.cliCom.write(b'sensorStop 0\n')
        
        buffer = b''
        start = time.time()
        while time.time() - start < timeout:
            data = self.cliCom.read(self.cliCom.in_waiting or 1)
            clean = data.replace(b'\x00', b'')
            if clean:
                buffer += clean
            # Wait for Done AND the next prompt before proceeding
            if b'Done' in buffer and b'mmwDemo:/>' in buffer:
                print("✓ Sensor stopped")
                time.sleep(0.2)  # small margin after prompt
                return True
            time.sleep(0.05)
        
        raise TimeoutError("sensorStop did not confirm")

    def warm_reset_and_wait(self):
        print("Sending warm reset...")
        port_name = self.cliCom.port
        
        # Send reset char by char at current baudrate
        cmd = 'sensorWarmRst 1\n'
        self.cliCom.reset_input_buffer()
        if self.cliCom.baudrate == 1250000:
            for char in cmd:
                time.sleep(0.001)
                self.cliCom.write(char.encode())
        else:
            self.cliCom.write(cmd.encode())
        
        # Wait for null bytes confirming reset fired
        print("  Waiting for null bytes...")
        start = time.time()
        while time.time() - start < 3.0:
            raw = self.cliCom.read(self.cliCom.in_waiting or 1)
            if b'\x00' in raw:
                print("  ✓ Reset firing")
                break
            time.sleep(0.01)
        
        # Close ports cleanly
        print("  Closing ports...")
        self.cliCom.close()
        if self.dataCom and self.dataCom is not self.cliCom:
            self.dataCom.close()
        
        time.sleep(0.5)
        print("  ✓ Ports closed, letting device boot...")
    
    def redetect_ports(self):
        """Re-run port detection after warm reset — mirrors what happens on first boot."""
        print("  Re-detecting COM ports...")
        parserType, cliCom, dataCom = self.detect_and_open_COM_ports()
        print(f"  ✓ Redetected: parserType={parserType}")
        self.parserType = parserType
        self.cliCom = cliCom
        self.dataCom = dataCom
        return parserType, cliCom, dataCom
    
    
