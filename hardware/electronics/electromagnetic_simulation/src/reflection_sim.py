import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.utils.utils import TimeSeries
from src.emission_sim import ChirpGenerator
from src.antenna_sim import ElectromagneticSim
import numpy as np
import matplotlib.pyplot as plt
import tempfile


def resolve_saved_path(path):
    """
    Anchor a relative save path to the project root and make sure its
    directory exists. openEMS chdirs into its Sim_Path during FDTD.Run and
    never restores the cwd, so relative paths cannot be trusted here.
    """
    if not os.path.isabs(path):
        path = os.path.join(PROJECT_ROOT, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path

class RadarResponseSynthesizer:
    def __init__(self, transfer_function_array, f, distance_first_object):
        """
        transfer_function_dict: {frequency: complex_transfer_coefficient}
        Example: {58e9: 0.3+0.1j, 58.1e9: 0.31+0.09j, ...}
        """

        self.transfer_function_array = transfer_function_array
        self.frequencies = f
        self.distance_first_object = distance_first_object
    
    def apply_to_chirp(self, tx_chirp_timeseries, time_step):
        """
        tx_chirp_timeseries: Your ChirpGenerator output (time domain)
        time_step: Time step in seconds (e.g., 1e-5 * 1e-6 for µs)
        
        Returns: Received signal in time domain
        """
        # 1. Get FFT of TX chirp
        tx_signal = np.array(tx_chirp_timeseries)
        tx_fft = np.fft.fft(tx_signal)
        freqs = np.fft.fftfreq(len(tx_signal), d=time_step)
        
        # 2. Interpolate transfer function to match FFT frequencies
        # Only use positive frequencies
        positive_mask = freqs >= 0
        positive_freqs = freqs[positive_mask]
        
        RX_list = []

        # Interpolate (linear or cubic)
        for i in range(self.transfer_function_array.shape[0]):
            transfer_interp = np.interp(
                positive_freqs,
                self.frequencies,
                np.abs(self.transfer_function_array[i])  # Magnitude
            ) * np.exp(1j * np.interp(
                positive_freqs,
                self.frequencies,
                np.angle(self.transfer_function_array[i])  # Phase
            ))
        
            # 3. Apply transfer function in frequency domain
            rx_fft = tx_fft.copy()
            rx_fft[positive_mask] *= transfer_interp
            
            # Mirror for negative frequencies (keep conjugate symmetry)
            rx_fft[~positive_mask] = np.conj(rx_fft[positive_mask][1:][::-1])
            
            # 4. Inverse FFT to get time-domain response
            rx_signal = np.fft.ifft(rx_fft)

            RX_list.append(np.real(rx_signal)) # Should be real for physical signal
        
        RX_signal_array = np.array(RX_list)
        
        return RX_signal_array  

    def apply_to_chirp_direct(self, tx_chirp_generator: ChirpGenerator):
        """
        tx_chirp_generator: Your ChirpGenerator object
        
        This has both:
        - tx_chirp_generator (the signal values)
        - tx_chirp_generator.ffs (the instantaneous frequencies)
        """
        time_step = tx_chirp_generator.time_step*1e-6
        tx_signal = np.array(tx_chirp_generator)
        instantaneous_freqs = np.array(tx_chirp_generator.ffs) * 1e9  # Convert GHz to Hz

        first_time = 2*self.distance_first_object/3e8
        
        # Apply transfer function based on instantaneous frequency
        RX_list = []

        for j in range(self.transfer_function_array.shape[0]):
            rx_signal = np.zeros_like(tx_signal, dtype=complex)
            for i, (amplitude, freq) in enumerate(zip(tx_signal, instantaneous_freqs)):
                if i*time_step < first_time:
                    rx_signal[i] = 0.0
                else: 
                    # Get transfer function at this instantaneous frequency
                    transfer = np.interp(
                        freq,
                        self.frequencies,
                        np.abs(self.transfer_function_array[j])
                    ) * np.exp(1j * np.interp(
                        freq,
                        self.frequencies,
                        np.angle(self.transfer_function_array[j])
                    ))
                    
                    rx_signal[i] = amplitude * transfer
            
            RX_list.append(np.real(rx_signal))
        RX_signal_array = np.array(RX_list)
        return RX_signal_array
    
    def sum_signals(self, RX_signal_array):
        return RX_signal_array[:3] + RX_signal_array[3:]

    def apply_to_chirp_stft(self, tx_chirp_generator: ChirpGenerator, 
                         window_size=131072, hop_size=None, target_max_distance=0.5):
        """
        Applique la transfer function en utilisant STFT pour préserver la causalité.
        
        :param tx_chirp_generator: Générateur du chirp TX
        :param window_size: Taille de la fenêtre STFT (en échantillons)
        :param hop_size: Pas entre fenêtres (défaut: window_size // 2 pour 50% overlap)
        :param target_max_distance: Distance max de la cible (pour vérifier la taille de fenêtre)
        """
        tx_signal = np.array(tx_chirp_generator)
        time_step = tx_chirp_generator.time_step * 1e-6  # µs → secondes
        N = len(tx_signal)
        
        if hop_size is None:
            hop_size = window_size // 2  # 50% overlap par défaut
        
        # Vérifier que la fenêtre est assez grande pour le délai max
        c = 3e8
        tau_max = 2 * target_max_distance / c
        samples_delay_max = int(np.ceil(tau_max / time_step))
        
        if window_size < 4 * samples_delay_max:
            print(f"Warning: window_size ({window_size}) peut être trop petit "
                f"pour distance={target_max_distance}m (délai={samples_delay_max} samples)")
        
        # Pré-calculer les phases unwrappées pour chaque canal
        unwrapped_phases = []
        for j in range(self.transfer_function_array.shape[0]):
            unwrapped_phases.append(
                np.unwrap(np.angle(self.transfer_function_array[j]))
            )
        
        # Fenêtre d'analyse (Hann pour smooth overlap-add)
        window = np.hanning(window_size)
        
        # Fréquences pour cette taille de fenêtre
        freqs_window = np.fft.fftfreq(window_size, d=time_step)
        
        # Pré-calculer H(f) interpolée pour chaque canal
        H_interpolated = []
        for j in range(self.transfer_function_array.shape[0]):
            H_mag = np.interp(
                np.abs(freqs_window),
                self.frequencies,
                np.abs(self.transfer_function_array[j])
            )
            H_phase = np.interp(
                np.abs(freqs_window),
                self.frequencies,
                unwrapped_phases[j]
            )
            # Conjugué pour fréquences négatives
            H_phase_signed = H_phase * np.sign(freqs_window + 1e-20)
            H = H_mag * np.exp(1j * H_phase_signed)
            H_interpolated.append(H)
        
        RX_list = []
        
        for j in range(self.transfer_function_array.shape[0]):
            # Buffer de sortie (avec padding pour le délai)
            output_length = N + window_size
            rx_signal = np.zeros(output_length)
            window_sum = np.zeros(output_length)  # Pour normalisation overlap-add
            
            # Parcourir le signal par fenêtres
            num_windows = (N - window_size) // hop_size + 1
            
            for win_idx in range(num_windows):
                start = win_idx * hop_size
                end = start + window_size
                
                # Extraire et fenêtrer le segment TX
                tx_segment = tx_signal[start:end] * window
                
                # FFT du segment
                tx_fft = np.fft.fft(tx_segment)
                
                # Appliquer H(f)
                rx_fft = tx_fft * H_interpolated[j]
                
                # IFFT
                rx_segment = np.real(np.fft.ifft(rx_fft))
                
                # Overlap-add dans le buffer de sortie
                rx_signal[start:start + window_size] += rx_segment * window
                window_sum[start:start + window_size] += window ** 2
            
            # Traiter la dernière fenêtre partielle si nécessaire
            remaining = N - num_windows * hop_size
            if remaining > 0:
                start = num_windows * hop_size
                # Padding avec des zéros
                tx_segment = np.zeros(window_size)
                tx_segment[:N - start] = tx_signal[start:] * window[:N - start]
                
                tx_fft = np.fft.fft(tx_segment)
                rx_fft = tx_fft * H_interpolated[j]
                rx_segment = np.real(np.fft.ifft(rx_fft))
                
                rx_signal[start:start + window_size] += rx_segment * window
                window_sum[start:start + window_size] += window ** 2
            
            # Normaliser par la somme des fenêtres (évite les artefacts overlap-add)
            # Éviter division par zéro
            window_sum = np.maximum(window_sum, 1e-10)
            rx_signal = rx_signal / window_sum
            
            # Tronquer à la longueur originale (garder le délai au début)
            rx_signal = rx_signal[:N]
            
            RX_list.append(rx_signal)
        
        return np.array(RX_list)

class RXSignals:
    def __init__(self, rx_signal_chirp_plus, rx_signal_chirp_moins):
        self.rx_signal_chirp_plus = rx_signal_chirp_plus
        self.rx_signal_chirp_moins = rx_signal_chirp_moins
        return


class SingleSignalReflectionSim(TimeSeries):
    def __init__(
            self, 
            transfer_dict:dict, 
            TX_chirp: ChirpGenerator, 
            time_step=1e-5,
            distance_first_object=0.015,
            force_recalculate = False,
            save_path = "saved/rx_signal.npy"
        ):
        """
        Docstring for __init__
        
        Time step of the simulation is in usec. So the default parameter for time_step is 1e-5 usec = 1e-11 sec
        
        :param self: Description
        :param time_step: Description
        """
        super().__init__(time_step=time_step)
        self.transfer_dict = transfer_dict
        
        self.f = self.transfer_dict["frequencies"]
        self.transfer_function_array = self.transfer_dict["transfer_function_array"]
        self.save_path = save_path
        
        self.TX_chirp = TX_chirp

        self.distance_first_object = distance_first_object
        self.force_recalculate = force_recalculate
        self.load_reflection_sim(
            distance_first_object = distance_first_object,
            force_recalculate=force_recalculate, 
            save_path=save_path
        )
        return 

    def load_reflection_sim(self, distance_first_object, force_recalculate=True, save_path="saved/rx_signal.npy"):
        """
        Docstring for load_reflection_sim
        Returns a RXSignals object

        :param self: Description
        :param force_recalculate: Description
        """
        save_path = resolve_saved_path(save_path)
        if os.path.exists(save_path) and not force_recalculate:
            rx_signal = np.load(save_path)
        else:
            # Calculate the array
            rx_signal = self.compute_reflection(
                transfer_function=self.transfer_function_array, 
                distance_first_object = distance_first_object,
                save=True, 
                save_path=save_path
            )

        self.rx_signal = rx_signal

        return rx_signal
        
    def compute_reflection(self, transfer_function, distance_first_object, save=True, save_path = 'saved/rx_signal.npy'):
        transfer_function_array = transfer_function
        synthesizer = RadarResponseSynthesizer(
            transfer_function_array, 
            f=self.f, 
            distance_first_object=distance_first_object
        )
        rx_signal = synthesizer.apply_to_chirp_direct(self.TX_chirp)
        rx_signal = synthesizer.sum_signals(rx_signal)
        if save:
            np.save(resolve_saved_path(save_path), rx_signal)

        return rx_signal
        
    def plot_reflection_sim(self):
        rx_signal=self.load_reflection_sim(
            force_recalculate=False, 
            save_path=self.save_path, 
            distance_first_object=self.distance_first_object
        )

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 20))

        y_list = self.TX_chirp.get_time_list()

        ax1.plot(y_list, self.TX_chirp, 'k-', label="TX chirp")

        rx = rx_signal

        ax2.plot(y_list, rx[0], 'k-', label="TX_1+TX_2, RX_1")
        ax2.plot(y_list, rx[1], 'b-', label="TX_1+TX_2, RX_2")
        ax2.plot(y_list, rx[2], 'r-', label="TX_1+TX_2, RX_3")

        for axi in [ax1, ax2]:
            axi.legend(loc=1)
            axi.grid()
            
        plt.show()
        return



class FullReflectionSim(TimeSeries):
    def __init__(
            self, 
            transfer_dict:dict, 
            TX_chirp: ChirpGenerator, 
            time_step=1e-5, 
            force_recalculate = False
        ):
        """
        Docstring for __init__
        
        Time step of the simulation is in usec. So the default parameter for time_step is 1e-5 usec = 1e-11 sec
        
        :param self: Description
        :param time_step: Description
        """
        super().__init__(time_step=time_step)
        self.transfer_dict = transfer_dict
        
        self.f = self.transfer_dict["frequencies"]
        self.transfer_function_array_plus = self.transfer_dict["transfer_function_array_+"]
        self.transfer_function_array_moins = self.transfer_dict["transfer_function_array_-"]

        self.TX_chirp = TX_chirp
        self.load_reflection_sim(force_recalculate=force_recalculate)
        return 

    def load_reflection_sim(self, force_recalculate=True):
        """
        Docstring for load_reflection_sim
        Returns a RXSignals object

        :param self: Description
        :param force_recalculate: Description
        """
        save_path_plus = resolve_saved_path('saved/rx_signal_plus.npy')
        save_path_moins = resolve_saved_path('saved/rx_signal_moins.npy')

        if os.path.exists(save_path_plus) and os.path.exists(save_path_moins) and not force_recalculate:
            rx_signal_plus = np.load(save_path_plus)
            rx_signal_moins = np.load(save_path_moins)
        else:
            # Calculate the array
            rx_signal_plus = self.compute_reflection(
                transfer_function=self.transfer_function_array_plus,
                save=True,
                save_path=save_path_plus
            )
            rx_signal_moins = self.compute_reflection(
                transfer_function=self.transfer_function_array_moins,
                save=True,
                save_path=save_path_moins
            )

        self.rx_signal_plus = rx_signal_plus
        self.rx_signal_moins = rx_signal_moins

        rx_signals = RXSignals(
            rx_signal_chirp_plus=self.rx_signal_plus,
            rx_signal_chirp_moins=self.rx_signal_moins
        )

        return rx_signals
        
    def compute_reflection(self, transfer_function, save=True, save_path = 'saved/rx_signal.npy'):
        transfer_function_array = transfer_function
        synthesizer = RadarResponseSynthesizer(
            distance_first_object=0.015,
            transfer_function_array=transfer_function_array, 
            f=self.f
        )
        rx_signal = synthesizer.apply_to_chirp_direct(self.TX_chirp)
        rx_signal = synthesizer.sum_signals(rx_signal)
        if save:
            np.save(resolve_saved_path(save_path), rx_signal)
        return rx_signal
        
    def plot_reflection_sim(self):
        rx_signals=self.load_reflection_sim(force_recalculate=False)

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 20))

        y_list = self.TX_chirp.get_time_list()

        ax1.plot(y_list, self.TX_chirp, 'k-', label="TX chirp")

        rx_plus = rx_signals["plus"]
        rx_moins = rx_signals["moins"]
        
        ax2.plot(y_list, rx_plus[0], 'k-', label="TX_1+TX_2, RX_1")
        ax2.plot(y_list, rx_plus[1], 'b-', label="TX_1+TX_2, RX_2")
        ax2.plot(y_list, rx_plus[2], 'r-', label="TX_1+TX_2, RX_3")
        ax3.plot(y_list, rx_moins[0], 'g-', label="TX_1-TX_2, RX_1")
        ax3.plot(y_list, rx_moins[1], 'c-', label="TX_1-TX_2, RX_2")
        ax3.plot(y_list, rx_moins[2], 'm-', label="TX_1-TX_2, RX_3")

        for axi in [ax1, ax2, ax3]:
            axi.legend(loc=1)
            axi.grid()
            
        plt.show()
        return




if __name__ == "__main__":

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
    tx1_plus_tx2_sim = ElectromagneticSim(
        Sim_Path=os.path.join(tempfile.gettempdir(), 'test1', 'tx1_plus_tx2'),
        antennas_to_excite={
            "TX1":1,
            "TX2":1,
        },
        show_geometry=False
    )
    tx1_plus_tx2_sim.FDTD_setup()
    transfer_dict = tx1_plus_tx2_sim.calculate_transfer_function(show_graph=False)

    reflection_sim = SingleSignalReflectionSim(
        transfer_dict=transfer_dict, 
        TX_chirp=TX_chirp,
        save_path = "saved/rx_signal.npy",
        force_recalculate=False,
        distance_first_object=0.015
    )
    reflection_sim.plot_reflection_sim()
