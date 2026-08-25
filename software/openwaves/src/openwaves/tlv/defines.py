"""TLV type identifiers emitted by IWRL6432 mmWave demo firmware.

These integer IDs are protocol facts of the TI mmWave demo UART output
format (and of the OpenWaves custom firmware for type 601).
"""

# Frame magic word as it appears on the wire (little-endian uint16 sequence
# 0x0102, 0x0304, 0x0506, 0x0708).
MAGIC_WORD = b"\x02\x01\x04\x03\x06\x05\x08\x07"

# Frame header: magic (Q) + version, totalPacketLen, platform, frameNumber,
# timeCpuCycles, numDetectedObj, numTLVs, subFrameNumber (8I) = 40 bytes.
FRAME_HEADER_STRUCT = "<Q8I"
FRAME_HEADER_SIZE = 40
TLV_HEADER_STRUCT = "<2I"
TLV_HEADER_SIZE = 8

# Frames are padded to a multiple of this size for transmission uniformity.
FRAME_PADDING = 32

# --- OpenWaves custom TLVs (emitted by the in-repo firmware) --------------
CAPON_SPECTRUM_3D_HEATMAP = 601
#: shape of the capon heatmap when it has the standard 5120 floats
CAPON_HEATMAP_SHAPE = (10, 32, 16)  # (depth slices, height, width)

# --- Legacy mmWave demo TLVs ---------------------------------------------
DETECTED_POINTS = 1
RANGE_PROFILE = 2
NOISE_PROFILE = 3
AZIMUTH_STATIC_HEAT_MAP = 4
RANGE_DOPPLER_HEAT_MAP = 5
STATS = 6
DETECTED_POINTS_SIDE_INFO = 7
AZIMUTH_ELEVATION_STATIC_HEAT_MAP = 8
TEMPERATURE_STATS = 9

# --- xWRL6432 out-of-box / MPD demo TLVs ---------------------------------
EXT_DETECTED_POINTS = 301
EXT_RANGE_PROFILE_MAJOR = 302
EXT_RANGE_PROFILE_MINOR = 303
EXT_RANGE_AZIMUT_HEAT_MAP_MAJOR = 304
EXT_RANGE_AZIMUT_HEAT_MAP_MINOR = 305
EXT_STATS = 306
EXT_PRESENCE_INFO = 307
EXT_TARGET_LIST = 308
EXT_TARGET_INDEX = 309
EXT_MICRO_DOPPLER_RAW_DATA = 310
EXT_MICRO_DOPPLER_FEATURES = 311
EXT_RADAR_CUBE_MAJOR = 312
EXT_RADAR_CUBE_MINOR = 313
EXT_POINT_CLOUD_INDICES = 314
EXT_ENHANCED_PRESENCE_INDICATION = 315
EXT_ADC_SAMPLES = 316
EXT_CLASSIFIER_INFO = 317
EXT_RX_CHAN_COMPENSATION_INFO = 318

# --- 3D people-tracking demo TLVs ----------------------------------------
SPHERICAL_POINTS = 1000
TRACKERPROC_3D_TARGET_LIST = 1010
TRACKERPROC_TARGET_INDEX = 1011
TRACKERPROC_TARGET_HEIGHT = 1012

# --- Target-index magic values (column 7 of the point cloud) -------------
TRACK_INDEX_WEAK_SNR = 253  # not associated, SNR too weak
TRACK_INDEX_BOUNDS = 254  # not associated, outside boundary of interest
TRACK_INDEX_NOISE = 255  # not associated, considered noise

#: number of classes reported by the MPD demo classifier TLV
NUM_CLASSES_IN_CLASSIFIER = 2
