import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.reflection_sim import RXSignals
from src.emission_sim import ChirpGenerator
from scipy.signal import butter, filtfilt

import numpy as np
import matplotlib.pyplot as plt



class RFReceiverSim:
    def __init__(self, tx_signal:ChirpGenerator, rx_signals:RXSignals):
        
        self.tx_signal = tx_signal
        self.rx_signals = rx_signals

        self.S = self.tx_signal.frequency_slope
        self.time_step = self.tx_signal.time_step*1e-6

        self.rx_plus = self.rx_signals.rx_signal_chirp_plus
        self.rx_moins = self.rx_signals.rx_signal_chirp_moins
        self.gain = 6.5-7 # dB

        self.fs = 1e5

        self.adc_sample_rate = 12.5 # MHz
        bit_depth = 12
        self.levels = 2 ** bit_depth

        self.ADC_start_sample = 37
        self.ADC_sample_buffer_size = 256

        return

    # ============================== RF process methods ==============================
    # ====== LNA method ======
    def low_noise_amplifier(self):
        gained_plus = self.rx_plus*(10**self.gain)
        gained_moins = self.rx_moins*(10**self.gain)
        self.gained_plus = gained_plus
        self.gained_moins = gained_moins
        return {
            "plus":self.gained_plus,
            "moins":self.gained_moins
        }
    
    # ====== Mixer method ======
    def mixer(self):
        TX = np.array(self.tx_signal).reshape((1,len(self.tx_signal)))
        RX_plus = self.gained_plus
        RX_moins = self.gained_moins
        mixed_signals_plus = RX_plus * TX
        mixed_signals_moins = RX_moins * TX
        self.mixed_signals_plus = mixed_signals_plus
        self.mixed_signals_moins = mixed_signals_moins
        return {
            "plus":self.mixed_signals_plus,
            "moins":self.mixed_signals_moins
        }
    
    # ====== Low Pass filter method ======
    def low_pass_filter(self, order=2):
        """
        IF low-pass filter with 5 MHz bandwidth (from spec sheet)
        """
        signal_plus = self.mixed_signals_plus
        signal_moins = self.mixed_signals_moins
        cutoff = 5e6/1e6  # 5 MHz (since the sim is in usec, then we have to divide by 1e-6)
        
        b, a = butter(order, cutoff, btype='low', analog=False, fs=self.fs) # Use a 2nd order butterworth filter
        filtered_plus = filtfilt(b, a, signal_plus)
        filtered_moins = filtfilt(b ,a ,signal_moins)
        self.IF_signal_plus = filtered_plus
        self.IF_signal_moins = filtered_moins
        
        return {
            "plus":self.IF_signal_plus,
            "moins":self.IF_signal_moins
        }
    
    # ====== ADC Methods methods ======
    def adc_sampler(self):
        """Sample analog signal at ADC rate"""
        sampling_period = 1 / self.adc_sample_rate
        downsample_ratio = int(sampling_period * self.fs)

        if downsample_ratio < 1:
            downsample_ratio = 1
        
        sampled_signal_plus = self.IF_signal_plus[:,::downsample_ratio]
        sampled_signal_moins = self.IF_signal_moins[:,::downsample_ratio]
        self.sample_time_list = [sampling_period*(i+self.ADC_start_sample) for i in range(self.ADC_sample_buffer_size)]
        
        # # Apply 12-bit quantization
        # sampled_signal = self._adc_quantize(sampled_signal)
        
        return {
            "plus":sampled_signal_plus,
            "moins":sampled_signal_moins
        }
    
    def _adc_quantize(self, signal):
        """(2^self.levels)-bit quantization"""
        # Assume signal range is [-1, 1] after normalization
        v_max = 1.0  # Full scale

        signal = np.array(signal)
        signal_max = np.array(np.max(signal,axis=1)).reshape(6,1)

        # Quantization step
        step = 2 * v_max / self.levels  # 2/4096 ≈ 0.000488
        
        # Quantize and clip
        normalized_signal = signal / signal_max

        quantized = np.round(normalized_signal*self.levels) * step
        quantized = np.clip(quantized, -v_max, v_max)

        self.adc_signal = quantized
        
        return self.adc_signal

    # ====== Summarized RF process methods ======
    def run(self):
        """
        Docstring for run
        
        Simulates the full Reception and treatment of the RF process

        :param self: Description
        """
        self.low_noise_amplifier()
        self.mixer()
        self.low_pass_filter(order=2)
        self.adc_data = self.adc_sampler()
        self.adc_data_plus = self.adc_data["plus"][:,self.ADC_start_sample:self.ADC_start_sample+self.ADC_sample_buffer_size]
        self.adc_data_moins = self.adc_data["moins"][:,self.ADC_start_sample:self.ADC_start_sample+self.ADC_sample_buffer_size]

        return {
            "plus":self.adc_data_plus,
            "moins":self.adc_data_moins
        }

    def get_time_list(self):
        if hasattr(self, "sample_time_list"):
            return self.sample_time_list
        else:
            self.run()
            return self.sample_time_list
    
    def plot_sampled_signal(self):

        signal_to_plot = self.adc_data_plus
        time_list = self.get_time_list()
        plt.plot(time_list, signal_to_plot[0])
        plt.plot(time_list, signal_to_plot[1])
        plt.plot(time_list, signal_to_plot[2])

        signal_to_plot = self.adc_data_moins
        plt.plot(time_list, signal_to_plot[0])
        plt.plot(time_list, signal_to_plot[1])
        plt.plot(time_list, signal_to_plot[2])

        plt.show()
        
        return


if __name__ == "__main__":
    rf_receiver_sim = RFReceiverSim(force_recalculate_reflection_sim=False)
    adc_data_dict = rf_receiver_sim.run()
    rf_receiver_sim.plot_sampled_signal()