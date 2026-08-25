import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rf_receiver_sim import RFReceiverSim
from matplotlib.widgets import Slider

import numpy as np
import matplotlib.pyplot as plt


class BPMDecoder:
    def __init__(self):
        return
    
    def binary_phase_decoding(self, adc_data_plus, adc_data_moins):
        adc_data_TX1 = (adc_data_plus + adc_data_moins)/2
        adc_data_TX2 = (adc_data_plus - adc_data_moins)/2

        adc_data = np.concatenate([adc_data_TX1, adc_data_TX2], axis=0)
        return adc_data
    

class RangeFFT:
    """
    Perform Range FFT on ADC data
    
    Parameters:
    -----------
    adc_data : ndarray of shape (num_antennas, num_samples)
                Example: (6, 256)
    nfft : int
            FFT size (usually same as num_samples)
    
    Returns:
    --------
    range_profile : ndarray of shape (num_antennas, nfft)
                    Complex FFT output for each antenna, complex output !!
    """
    def __init__(self, num_antennas = 6, num_samples = 256, nfft=128):
        self.num_antennas = num_antennas
        self.num_samples = num_samples
        self.nfft = nfft
        return
    
    def range_fft(self, adc_data):
        num_antennas, num_samples = adc_data.shape
        
        # Apply window to reduce spectral leakage
        window = np.hanning(num_samples)
        
        # Initialize output
        range_profile = np.zeros((num_antennas, self.nfft), dtype=complex)
        
        # FFT for each antenna
        for ant_idx in range(num_antennas):
            # Apply window
            windowed_data = adc_data[ant_idx, :] * window
            
            # Perform FFT
            fft_result = np.fft.fft(windowed_data, n=self.nfft)
            
            # Store result
            range_profile[ant_idx, :] = fft_result
        
        self.range_profile = range_profile
        return self.range_profile

    def get_range_bins(self, nfft=128):
        """
        Calculate range for each FFT bin
        
        Returns:
        --------
        ranges : ndarray
                Range in meters for each FFT bin
        """
        if hasattr(self, "ranges"):
            return self.ranges
        else:
            # Frequency resolution
            freq_resolution = self.fs / nfft  # Hz per bin
            
            # Frequency bins (only positive frequencies matter)
            freq_bins = np.arange(nfft) * freq_resolution
            
            # Range from beat frequency: R = (f_beat * c) / (2 * S)
            ranges = (freq_bins * 3e8) / (2 * self.S)
            self.ranges = ranges
            return self.ranges
    
    def get_magnitude_db(self):
        """
        Convert complex FFT to magnitude in dB
        
        Parameters:
        -----------
        range_profile : complex ndarray of shape (num_antennas, nfft)
        
        Returns:
        --------
        magnitude_db : ndarray of shape (num_antennas, nfft)
        """
        range_profile = self.range_profile
        magnitude = np.abs(range_profile)
        
        # Convert to dB (avoid log(0))
        magnitude_db = 20 * np.log10(magnitude + 1e-10)
        
        return magnitude_db
    
    def plot_range_profile(self, antenna_idx=0):
        """
        Plot range profile for a specific antenna
        
        Parameters:
        -----------
        adc_data : ndarray of shape (num_antennas, num_samples)
        antenna_idx : int, which antenna to plot (0-5)
        """        
        # Get range bins
        ranges = self.get_range_bins()
        
        # Get magnitude in dB
        magnitude_db = self.get_magnitude_db()
        
        # Plot (only positive frequencies = first half)
        num_bins = len(ranges) // 2
        
        plt.figure(figsize=(12, 5))
        plt.plot(ranges[:num_bins], magnitude_db[antenna_idx, :num_bins])
        plt.xlabel('Range (m)')
        plt.ylabel('Magnitude (dB)')
        plt.title(f'Range Profile - Antenna {antenna_idx}')
        plt.grid(True)
        plt.show()
    
    def plot_all_antennas(self):
        """
        Plot range profiles for all antennas
        """
        adc_data = self.adc_data
        
        num_antennas = adc_data.shape[0]
        
        # Perform Range FFT
        self.range_fft()
        ranges = self.get_range_bins()
        magnitude_db = self.get_magnitude_db()
        
        # Plot
        num_bins = len(ranges) // 2
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 8))
        axes = axes.flatten()
        
        for ant_idx in range(num_antennas):
            axes[ant_idx].plot(ranges[:num_bins], magnitude_db[ant_idx, :num_bins])
            axes[ant_idx].set_xlabel('Range (m)')
            axes[ant_idx].set_ylabel('Magnitude (dB)')
            axes[ant_idx].set_title(f'Antenna {ant_idx}')
            axes[ant_idx].grid(True)
        
        plt.tight_layout()
        plt.show()


class CaponBeamforming:
    def __init__(self, N_range_bins=10):
        self.N_range_bins = N_range_bins
        return
    
        # ====== Capon BF methods ======
    
    def _calculate_covariance_matrix(self, range_profile):
        """
        Docstring for _calculate_covariance_matrix
        This function calculates the covariance matrix for a single chirp
        Returns the square matrix (N_range_bins, n, n) where n is number of virtual antennas

        :param self: Description
        :param range_profile: Description (expected shape: (n_antennas, n_range_bins))
        """        
        # range_profile should be (n_antennas, n_range_bins)
        # We calculate the spatial covariance matrix 
        # (we should normally average by N the number of snapshots, but since we are simulating, 
        # we don't have any noise so no need to average)
        n_antennas, n_range_bins = range_profile.shape
        R = np.zeros((n_range_bins, n_antennas, n_antennas), dtype=complex)
        
        for i in range(n_range_bins):
            # Outer product for each range bin
            x = range_profile[:, i:i+1]  # Shape: (n_antennas, 1)
            R[i] = x @ x.conj().T  # Shape: (n_antennas, n_antennas)
        
        return R  # Shape: (n_range_bins, n_antennas, n_antennas)
        
    def _calculate_inverse_square_matrix(self, R):
        """
        Docstring for _calculate_inverse_square_matrix
        This function calculates the inverse of the covariance matrix R.
        Returns the square matrix (N_range_bins, n, n) where n is number of virtual antennas

        Applies the epsilon regularisation to assure invertability

        :param self: Description
        :param R: Description
        Inputs the range dependent R matrix (N_range_bins, n, n)
        """
        N_range_bins, n_antennas, _ = R.shape
    
        # Calculate epsilon for each range bin
        # np.trace with axis1 and axis2 computes trace for each matrix in the stack
        traces = np.trace(R, axis1=1, axis2=2)  # Shape: (N_range_bins,)
        epsilon = 1e-6 * traces / n_antennas  # Shape: (N_range_bins,)
        
        # Add regularization (broadcasting handles the range dimension)
        eye_matrix = np.eye(n_antennas)
        R_reg = R + epsilon[:, np.newaxis, np.newaxis] * eye_matrix
        
        # Vectorized inverse (numpy handles batch inversion)
        R_inv = np.linalg.inv(R_reg)
        
        return R_inv
    
    def _calculate_steering_vector(self, theta, phi):
        """
        Docstring for _calculate_steering_vector
        
        Calculates the steering vector of size (n, 1) where n is the number of antennas

        :param self: Description
        :param theta: Description (elevation angle in degrees)
        :param phi: Description (azimuth angle in degrees)
        """
        lambda_antenna = 4.836
        spacing = lambda_antenna/2
        num_antennas = 6
        a_theta_phi = np.zeros((num_antennas, 1), dtype=complex)
        
        antenna_coordinates = {
            0: (0, 0), 
            1: (1*spacing, 1*spacing),
            2: (0, 2*spacing),
            3: (0, 1*spacing),
            4: (1*spacing, 2*spacing),
            5: (0, 3*spacing),
        }
        
        # Convert angles to radians
        theta_rad = np.deg2rad(theta)
        phi_rad = np.deg2rad(phi)
        
        f_theta = np.sin(theta_rad)
        cos_phi = np.cos(phi_rad)
        sin_phi = np.sin(phi_rad)
        
        for i in range(num_antennas):
            psi_n = 2 * np.pi / lambda_antenna * f_theta * (
                antenna_coordinates[i][0] * cos_phi + antenna_coordinates[i][1] * sin_phi
            )
            a_theta_phi[i, 0] = np.exp(1j * psi_n)  # This is cleaner than cos + j*sin
            # Or equivalently: a_theta_phi[i, 0] = np.cos(psi_n) + 1j * np.sin(psi_n)
        
        return a_theta_phi
    
    def _calculate_P_theta_phi(self, R_inv, a_theta_phi):
        """
        Docstring for _calculate_P_theta_phi
        
        Calculates the 1/(a^H * R_inv * a) shape : (N_range_bins,)
        Returns P_theta_phi

        :param self: Description
        :param R_inv: Description (shape: (N_range_bins, n, n))
        :param a_theta_phi: Description (shape: (n, 1))
        :return: P_theta_phi of shape (N_range_bins,)
        """
        # a^H shape: (1, n_antennas)
        a_H = a_theta_phi.conj().T
        
        # Vectorized matrix multiplication for all range bins
        # np.einsum is efficient for this batched operation
        # 'ij,kjl,lm->kim' means: a_H @ R_inv[k] @ a for all k
        denominator = np.einsum('ij,kjl,lm->k', a_H, R_inv, a_theta_phi)
        
        # CAPON output power is the reciprocal
        P_theta_phi = 1.0 / np.abs(denominator)
        
        return P_theta_phi

    def capon_beamforming(self, range_profile):
        """
        Docstring for capon_beamforming

        Performs the capon beamforming (MVDR) algorithm on the range profile
        Returns the capon beamformed matrix 3D heatmap of the spectral density 
        of size (N_range_bins, N_theta, N_phi), where :
            - N_range_bins is the number of range bins of the range profile
            - N_theta is the elevation resolution
            - N_phi is the azimuth resolution
        
        :param self: Description
        """
        N_range_bins = range_profile.shape[1]
        
        # Calculate covariance matrix once for all range bins
        R = self._calculate_covariance_matrix(range_profile=range_profile)
        R_inv = self._calculate_inverse_square_matrix(R=R)

        theta_max = 60
        theta_min = 0
        N_theta = 16
        theta_res = (theta_max - theta_min) / N_theta

        phi_max = 180
        phi_min = -180
        N_phi = 32
        phi_res = (phi_max - phi_min) / N_phi

        snapshot = np.zeros((N_range_bins, N_theta, N_phi))
        
        for ind_theta in range(N_theta):
            theta = theta_min + theta_res * ind_theta
            for ind_phi in range(N_phi):
                phi = phi_min + phi_res * ind_phi  # Fixed: was using theta_min instead of phi_min

                a_theta_phi = self._calculate_steering_vector(theta=theta, phi=phi)
                P_theta_phi = self._calculate_P_theta_phi(R_inv=R_inv, a_theta_phi=a_theta_phi)
                
                # P_theta_phi has shape (N_range_bins,) - one value per range bin
                snapshot[:, ind_theta, ind_phi] = P_theta_phi

        self.capon_3D_heatmap = snapshot
        # self.capon_3D_heatmap = np.flip(self.capon_3D_heatmap, axis=1)
        return self.capon_3D_heatmap
   
    def calibrate(self, range_bin=0):
        """
        Store a reference measurement for calibration.
        Use a close, uniform reflector to capture the antenna pattern.
        """
        # Store the reference (add small epsilon to avoid division by zero)
        self.calibration_pattern = self.capon_3D_heatmap[range_bin, :, :] + 1e-10
        return

    def apply_calibration(self):
        return
    

class RadarOutputVisualizer:
    def __init__(
            self,
            db_scale=False, 
            vmin=None, 
            vmax=None, 
            min_range_bin=1, 
            max_range_bin = 10, 
        ):
        self.db_scale = db_scale
        self.vmin = vmin
        self.vmax = vmax
        self.min_range_bin = min_range_bin
        self.max_range_bin = max_range_bin
        return
    
    def visualize_capon_3D_heatmap(
            self, 
            capon_3D_heatmap,
        ):
        """
        Visualize the 3D CAPON beamforming heatmap with an interactive slider.
        
        :param db_scale: If True, display in dB scale (10*log10)
        :param vmin: Minimum value for colorbar (None for auto)
        :param vmax: Maximum value for colorbar (None for auto)
        """
        db_scale = self.db_scale
        vmin = self.vmin
        vmax = self.vmax
        min_range_bin = self.min_range_bin
        max_range_bin = self.max_range_bin

        if capon_3D_heatmap is None:
            print("Error: No CAPON heatmap available. Run capon_beamforming() first.")
            return
        
        # Get data dimensions
        N_range_bins, N_theta, N_phi = capon_3D_heatmap.shape
        
        # Convert to dB scale if requested
        if db_scale:
            data = 10 * np.log10(capon_3D_heatmap[:max_range_bin,:,:] + 1e-10)  # Add small epsilon to avoid log(0)
            scale_label = 'Power (dB)'
        else:
            data = np.flip(capon_3D_heatmap[min_range_bin-1:max_range_bin,:,:], axis=1)
            scale_label = 'Power (linear)'
        
        # Set colorbar limits
        if vmin is None:
            vmin = data.min()
        if vmax is None:
            vmax = data.max()
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 8))
        plt.subplots_adjust(bottom=0.15)
        
        # Display initial heatmap
        im = ax.imshow(data[0], cmap='hot', aspect='auto', 
                    interpolation='nearest', vmin=vmin, vmax=vmax,
                    origin='lower', extent=[-180, 180, 60, 0])
        
        # Configure axes
        ax.set_xlabel('Azimuth (φ) [degrees]', fontsize=12)
        ax.set_ylabel('Elevation (θ) [degrees]', fontsize=12)
        ax.set_title(f'CAPON Beamforming - Range Bin 0/{N_range_bins-1}', fontsize=14)
        ax.grid(True, alpha=0.3)
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax, label=scale_label)
        
        # Create slider
        ax_slider = plt.axes([0.2, 0.05, 0.6, 0.03])
        slider = Slider(ax_slider, 'Range Bin', 0, max_range_bin-1, 
                        valinit=0, valstep=1)
        
        # Update function
        def update(val):
            idx = int(slider.val)
            im.set_data(data[idx])
            ax.set_title(f'CAPON Beamforming - Range Bin {idx}/{N_range_bins-1}')
            fig.canvas.draw_idle()
        
        # Connect slider
        slider.on_changed(update)
        
        plt.show()

    def visualize_capon_3D_polar(
            self,
            capon_3D_heatmap,
        ):
        """
        Visualize the 3D CAPON beamforming heatmap in polar coordinates.
        
        Center = 0° elevation, outer edge = max elevation.
        Azimuth follows mathematical convention (0° points right).
        
        :param db_scale: If True, display in dB scale (10*log10)
        :param vmin: Minimum value for colorbar (None for auto)
        :param vmax: Maximum value for colorbar (None for auto)
        :param max_range_bin: Maximum range bin to display
        """

        db_scale = self.db_scale
        vmin = self.vmin
        vmax = self.vmax
        min_range_bin = self.min_range_bin
        max_range_bin = self.max_range_bin
        
        if capon_3D_heatmap is None:
            print("Error: No CAPON heatmap available. Run capon_beamforming() first.")
            return
        
        # Get data dimensions
        N_range_bins, N_theta, N_phi = capon_3D_heatmap.shape
        
        # Convert to dB scale if requested
        if db_scale:
            data = 10 * np.log10(capon_3D_heatmap[:max_range_bin, :, :] + 1e-10)
            scale_label = 'Power (dB)'
        else:
            data = capon_3D_heatmap[:max_range_bin, :, :]
            scale_label = 'Power (linear)'
        
        # Set colorbar limits
        if vmin is None:
            vmin = data.min()
        if vmax is None:
            vmax = data.max()
        
        # Create azimuth and elevation arrays
        # Assuming azimuth goes from -180 to 180 and elevation from 0 to 60
        azimuth_deg = np.linspace(-180, 180, N_phi + 1)  # +1 for pcolormesh edges
        elevation_deg = np.linspace(0, 60, N_theta + 1)  # +1 for pcolormesh edges
        
        # Convert to polar coordinates
        # Azimuth -> angle (in radians)
        # Elevation -> radius
        azimuth_rad = np.deg2rad(azimuth_deg)
        radius = elevation_deg  # Elevation directly maps to radius
        
        # Create meshgrid for pcolormesh
        Az, R = np.meshgrid(azimuth_rad, radius)
        
        # Create figure with polar projection
        fig, ax = plt.subplots(figsize=(10, 9), subplot_kw={'projection': 'polar'})
        plt.subplots_adjust(bottom=0.12)
        
        # Set 0° to point right (mathematical convention) - this is default, but explicit
        ax.set_theta_zero_location('E')
        ax.set_theta_direction(1)  # Counter-clockwise
        
        # Plot initial heatmap
        mesh = ax.pcolormesh(Az, R, data[0], cmap='hot', vmin=vmin, vmax=vmax, shading='auto')
        
        # Configure axes
        ax.set_xlabel('Azimuth [degrees]', fontsize=12, labelpad=15)
        ax.set_title(f'CAPON Beamforming - Range Bin 0/{N_range_bins-1}', fontsize=14, pad=20)
        
        # Set radial label
        ax.set_ylabel('Elevation [degrees]', fontsize=12, labelpad=30)
        ax.set_rlabel_position(45)  # Move radial labels to avoid overlap
        
        # Colorbar
        cbar = plt.colorbar(mesh, ax=ax, label=scale_label, pad=0.1)
        
        # Create slider
        ax_slider = plt.axes([0.2, 0.03, 0.6, 0.03])
        slider = Slider(ax_slider, 'Range Bin', 0, max_range_bin - 1, valinit=0, valstep=1)
        
        # Update function
        def update(val):
            idx = int(slider.val)
            mesh.set_array(data[idx].ravel())
            ax.set_title(f'CAPON Beamforming - Range Bin {idx}/{N_range_bins-1}', fontsize=14, pad=20)
            fig.canvas.draw_idle()
        
        # Connect slider
        slider.on_changed(update)
        
        plt.show()


class DigitalProcess:
    def __init__(self):
        self.bpm_decoder = BPMDecoder()
        self.range_fft = RangeFFT()
        self.capon_beamformer = CaponBeamforming()
        self.radar_visualizer = RadarOutputVisualizer()
        return
    
    def run(self, adc_data_plus, adc_data_moins):
        adc_data = self.bpm_decoder.binary_phase_decoding(
            adc_data_plus=adc_data_plus,
            adc_data_moins=adc_data_moins
        )
        range_profile = self.range_fft.range_fft(adc_data=adc_data)
        capon_3D_heatmap = self.capon_beamformer.capon_beamforming(range_profile=range_profile)
        self.radar_visualizer.visualize_capon_3D_heatmap(capon_3D_heatmap=capon_3D_heatmap)
        return
    


if __name__ == "__main__":

    rf_receiver_sim = RFReceiverSim(force_recalculate_reflection_sim=False)
    adc_data_dict = rf_receiver_sim.run()

    dpc = DigitalProcess()
    dpc.run(
        adc_data_plus=adc_data_dict["plus"], 
        adc_data_moins=adc_data_dict["moins"]
    )
    