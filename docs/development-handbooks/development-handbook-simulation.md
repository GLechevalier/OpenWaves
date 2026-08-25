# Development handbook on electromagnetic simulation

The radar works; now it needs astronomical amounts of training data to
become robust. Answer: simulate the radar and the world in
[openEMS](https://www.openems.de) (FDTD, University of Duisburg-Essen)
and generate data forever. This log is the condensed version; the code
lives in `hardware/electronics/electromagnetic_simulation/`.

## Setup

Python 3.14 + openEMS. On Windows: unzip the openEMS release to
`~/opt/openEMS`, add it to PATH, `pip install` the CSXCAD and openEMS
wheels from its `python/` folder, set `OPENEMS_INSTALL_PATH`, verify with
`import openEMS` / `import CSXCAD` and by launching `AppCSXCAD`.

Workflow of every sim: import libraries, define geometry and excitation,
define the mesh (boundary conditions, time step, dump boxes), run, post-
process.

## Step 1: antenna design

Designed the 60 GHz series-fed microstrip patch antenna array from
scratch: patch antenna theory, quarter-wave transformers, phased array
design (Altium and ScienceDirect references in the original notes).
Compared the simulated radiation pattern against TI's measured data for
the board: good match.

## Step 2: hardware replication

Rebuilt the bench in the simulator, ticking through:

- Reflector and wall above the antenna; observed the TX1 Gaussian pulse
  reflection on RX1/RX2/RX3, with visualization videos.
- Chirp emission and BPM MIMO, using the real chirp parameters
  (58 to 61.88 GHz sweep).

### The trick that made it tractable

Full FDTD of one FMCW chirp is impossible: a 24.3 us chirp at 61.88 GHz
needs a ~1.6e-14 s time step, i.e. ~1.5 million steps, ~9.2 days per
simulation. Instead:

1. Excite each scene once with a Gaussian pulse and extract the full
   transfer function of the material stack: power vs frequency for each
   TX-RX pair (a 2D tensor: frequency x 6 channel pairs).
2. Multiply any excitation (the chirp) by that matrix.

Sanity check on linearity: nonlinear material effects appear at MW/cm2;
we are at mW/cm2, so pure transfer functions are valid.

### Rest of the chain

- BPM decoding, TX/RX mixing, and the ADC sampler (256 samples, matching
  the real buffer).
- Range FFT (3 cm range bins), then Capon beamforming: matrix inversion,
  problem reformulation, and reconstruction of the 3D image, compared
  against real measured data.

## Realism fixes and the big bug

- Modeled the plastic casing in front of the sensor.
- Reshaped the antennas to match the real directivity pattern.
- **Critical debug**: the TX2 → RX transfer functions were wrong, the
  simulation had only been excited from TX1. Found by comparing the
  apparent RX-TX spacing (11.7 / 10.8 mm vs the real 11.8 mm) and the
  Bode plots of the TX1+TX2 and TX1-TX2 BPM modes. Re-ran the sim with
  TX2 as the emitter: fixed.
- Checked reflection timing (waves arriving with delay): turned out to
  be correct already.
- Adjusted the absorbers around the antenna.
