import sys
import os

sys.path.append(os.getcwd())

import src.antenna_sim as openAntenna
import tempfile

elemectromagnetic_sim = openAntenna.ElectromagneticSim(
    Sim_Path=os.path.join(tempfile.gettempdir(), 'test1', 'tx1_plus_tx2'),
    show_geometry=True,
    antennas_to_excite={
        "TX1":1,
        "TX2":+1
    })

elemectromagnetic_sim.run() 
elemectromagnetic_sim.calculate_transfer_function(show_graph=True)
elemectromagnetic_sim.calculate_antenna_caracteristics()
elemectromagnetic_sim.show_voltage_static()
elemectromagnetic_sim.show_voltage_animated(save=True)