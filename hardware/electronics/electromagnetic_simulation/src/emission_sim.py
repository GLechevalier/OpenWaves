import sys
import os

sys.path.append(os.getcwd())

from src.utils.utils import TimeSeries
import matplotlib.pyplot as plt
import math
import numpy as np

class Emitter:
    def __init__(self):
        return
    

class FrequencyFunctionGenerator(TimeSeries):
    def __init__(
            self, 
            frequency_start, # GHz
            frequency_slope, # MHz/us
            TX_start_time, # usec
            ramp_end_time, # usec
            idle_time, # usec
            number_of_chirps, # 1
            time_step=0.1, 
            start_time=0
        ):
        super().__init__(time_step, start_time)
        self.frequency_start = frequency_start
        self.frequency_slope = frequency_slope
        self.max_freq = frequency_start + frequency_slope*ramp_end_time/1e3
        self.TX_start_time= TX_start_time
        self.ramp_end_time = ramp_end_time
        self.idle_time = idle_time
        self.number_of_chirps = number_of_chirps
        self.chirp_frequency = ramp_end_time + idle_time
        self.end_time = TX_start_time + number_of_chirps*self.chirp_frequency

        self.generate_function()

    def generate_function(self):
        total = int((self.end_time-self.start_time)//self.time_step)
        for i in range(total):
            time = i*self.time_step
            relative_chirp_time = (time-self.TX_start_time)%self.chirp_frequency
            if time<self.TX_start_time or relative_chirp_time>=self.ramp_end_time:
                self.append(self.frequency_start)
            elif relative_chirp_time<self.ramp_end_time:
                coeff = relative_chirp_time/self.ramp_end_time
                self.append(self.frequency_start + (self.max_freq-self.frequency_start)*coeff)
        return self
    
    def show(self):
        x_list = self
        y_list = self.get_time_list()
        plt.plot(y_list, x_list)
        plt.show()
        return
    

class ChirpGenerator(TimeSeries):
    def __init__(self, amplitude, offset, phase_offset, frequency_start, frequency_slope, TX_start_time, ramp_end_time, idle_time, number_of_chirps, time_step=0.1, start_time=0):
        super().__init__(time_step=time_step, start_time=start_time)
        ffs = FrequencyFunctionGenerator(
            frequency_start=frequency_start, 
            frequency_slope=frequency_slope, 
            TX_start_time=TX_start_time, 
            ramp_end_time=ramp_end_time, 
            idle_time=idle_time, 
            number_of_chirps=number_of_chirps,
            time_step=time_step,
            start_time=start_time
        )

        self.ffs = ffs
        self.frequency_start = frequency_start
        self.frequency_slope = frequency_slope
        self.max_freq = self.ffs.max_freq
        self.TX_start_time= TX_start_time
        self.ramp_end_time = ramp_end_time
        self.idle_time = idle_time
        self.number_of_chirps = number_of_chirps
        self.chirp_frequency = ramp_end_time + idle_time
        self.end_time = TX_start_time + number_of_chirps*self.chirp_frequency
    
        self.amplitude = amplitude
        self.offset = offset
        self.phase_offset=phase_offset
        self.frequency_input = ffs
        self.generate_time_function()

    def sinusoid(self, frequency, time):
        return self.amplitude*math.sin(2*math.pi*frequency*time + self.phase_offset)+self.offset

    def sinusoid_special(self, frequency, time):
        return self.amplitude*math.sin(2*math.pi*self.frequency_start*time + self.frequency_slope*time**2/2+ self.phase_offset)+self.offset

    def generate_time_function(self):
        total = int((self.end_time-self.start_time)//self.time_step)
        for i in range(total) :
            # print(self.frequency_input[i])
            self.append(self.sinusoid_special(frequency=self.frequency_input[i],time=i*self.time_step))

    def custom_excitation_function(self, time):
        return self.get(time*1e6)

    def show(self):
        x_list = self
        y_list = self.get_time_list()
        plt.plot(y_list, x_list)
        plt.show()
        return
    
    def show_fft(self):
        fft_result = np.fft.fft(tfg)
        fft_magnitude = np.abs(fft_result)/5*self.time_step
        frequencies = np.fft.fftfreq(len(tfg), d=self.time_step)
        positive_freqs = frequencies
        positive_magnitude = fft_magnitude
        # positive_freqs = frequencies[:len(frequencies)//2]
        # positive_magnitude = fft_magnitude[:len(fft_magnitude)//2]
        plt.figure(figsize=(10, 4))
        plt.plot(positive_freqs, positive_magnitude)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Magnitude')
        plt.title('Fourier Transform')
        plt.grid(True)
        plt.show()
        return
    

def FMCW_radar_demo():
    tfg = ChirpGenerator(
        amplitude=1,
        offset=0,
        phase_offset=0,
        frequency_start=58, 
        frequency_slope=160,
        TX_start_time=0, 
        ramp_end_time=24.3, 
        idle_time=28,
        number_of_chirps=1,
        time_step=1e-5, # usec ~1/(max_freq * 1000)
        start_time=0.0
    )

    distance = 70 # m
    delta_t = 2*distance/3e8*1e6

    tfg2 = ChirpGenerator(
        amplitude=1,
        offset=0,
        phase_offset=0,
        frequency_start=58, 
        frequency_slope=160,
        TX_start_time=delta_t, 
        ramp_end_time=24.3, 
        idle_time=28,
        number_of_chirps=1,
        time_step=1e-5, # usec ~1/(max_freq * 1000)
        start_time=0.0
    )
    
    arr1 = np.array(tfg)
    arr2 = np.array(tfg2)[:len(arr1)]

    arr3 = np.multiply(arr1, arr2)
    
    sampling_freq = 12.5 # MHz
    ratio = int(1/sampling_freq/1e-5)

    x_list = arr3[::ratio]
    y_list = tfg.get_time_list()[::ratio]
    
    n = 500
    fft_result = np.fft.fft(x_list, n=n, norm='forward')
    fft_magnitude = np.abs(fft_result)
    frequencies = np.fft.fftfreq(n, d=1/sampling_freq)
    positive_freqs = frequencies
    positive_magnitude = fft_magnitude
    
    plt.figure(figsize=(10, 4))
    plt.plot(positive_freqs, positive_magnitude)
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.title('Fourier Transform')
    plt.grid(True)
    plt.show()

    f = 0.0747
    x_smooth = [0.51*np.sin(2*np.pi*f*x+np.pi/2) for x in y_list]
    plt.plot(y_list, x_list)
    plt.plot(y_list, x_smooth)
    plt.show()
    
    S = 1601e12 # MHz/usec

    d = 3e8*f*1e6/(S*2)
    
    print("lambda = ", d)
    return

    
if __name__ == "__main__":
    tfg = ChirpGenerator(
        amplitude=1,
        offset=0,
        phase_offset=0,
        frequency_start=58, 
        frequency_slope=160,
        TX_start_time=0, 
        ramp_end_time=24.3, 
        idle_time=28,
        number_of_chirps=1,
        time_step=1e-5, # usec ~1/(max_freq * 1000)
        start_time=0.0
    )

    print(len(tfg))
    print(tfg.custom_excitation_function(52.29998/1e6))
    
    tfg.show()

    # tfg.show_fft()

    
        