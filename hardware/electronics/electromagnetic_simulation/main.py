import os
import sys

sys.path.append(os.getcwd())

from src.emission_sim import ChirpGenerator
from src.antenna_sim import ElectromagneticSim, TransferFunctionIdentifier
from src.reflection_sim import FullReflectionSim
from src.rf_receiver_sim import RFReceiverSim
from src.digital_processing import BPMDecoder, RangeFFT, CaponBeamforming, RadarOutputVisualizer
import tempfile

# Emit the chirp
TX_chirp = ChirpGenerator(
    amplitude=1,
    offset=0,
    phase_offset=0,
    frequency_start=58, 
    frequency_slope=160,
    TX_start_time=0, 
    ramp_end_time=24.3, 
    idle_time=1,
    number_of_chirps=1,
    time_step=1e-5, # usec ~1/(max_freq * 1000)
    start_time=0.0
)

# FDTD simulation to simulate the environement finely with Maxwell equations
tx1_plus_tx2_sim = ElectromagneticSim(
    Sim_Path=os.path.join(tempfile.gettempdir(), 'test1', 'tx1_plus_tx2'),
    antennas_to_excite={
        "TX1":1,
        "TX2":1,
    },
    show_geometry=False
)

tx1_moins_tx2_sim = ElectromagneticSim(
    Sim_Path=os.path.join(tempfile.gettempdir(), 'test1', 'tx1_moins_tx2'),
    antennas_to_excite={
        "TX1":1,
        "TX2":-1,
    },
    show_geometry=False
)

# tx1_plus_tx2_sim.run()
# tx1_moins_tx2_sim.run()

transfer_function_identifier = TransferFunctionIdentifier(
    electromagnetic_sim_plus=tx1_plus_tx2_sim,
    electromagnetic_sim_moins=tx1_moins_tx2_sim,
    force_run_sim=False
)
transfer_dict = transfer_function_identifier.calculate_transfer_function(show_graph=False)

# Pass the reflection sim
full_reflection_sim = FullReflectionSim(
    transfer_dict=transfer_dict, 
    TX_chirp=TX_chirp
)
rx_signals = full_reflection_sim.load_reflection_sim(force_recalculate=True)

# Receiver simulation
rf_receiver_sim = RFReceiverSim(
    tx_signal=TX_chirp,
    rx_signals=rx_signals,
)
adc_data_dict = rf_receiver_sim.run()

# Digital processing
bpm_decoder = BPMDecoder()
range_fft = RangeFFT()
capon_beamformer = CaponBeamforming()
radar_visualizer = RadarOutputVisualizer(max_range_bin=1)

adc_data = bpm_decoder.binary_phase_decoding(
    adc_data_plus=adc_data_dict["plus"],
    adc_data_moins=adc_data_dict["moins"]
)
range_profile = range_fft.range_fft(adc_data=adc_data)
capon_3D_heatmap = capon_beamformer.capon_beamforming(range_profile=range_profile)

# Visualize results
radar_visualizer.visualize_capon_3D_heatmap(capon_3D_heatmap=capon_3D_heatmap)