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

![CAD drawing of the series-fed two-patch element with dimensions](../../public/images/simulation/patch-antenna-cad.png)
*The series-fed two-patch element, dimensions in mm.*

![Sketch of the patch geometry parameters](../../public/images/simulation/patch-design-parameters.png)
*Parametrization of the element: patch width, interfeed length, and the
resulting patch-to-patch distance D.*

A single element simulated in openEMS resonates where it should:

![S11 of the single patch element](../../public/images/simulation/single-patch-s11.png)
*S11 of the single element: main resonance at ~60.5 GHz.*

![Radiation pattern of the single patch element at 60.5 GHz](../../public/images/simulation/single-patch-directivity.png)
*Directivity of the single element at 60.5 GHz (xz and yz planes).*

Then the full array (2 TX + 3 RX series-fed columns) was laid out in the
simulator:

![Layout of the antenna array in the simulation](../../public/images/simulation/antenna-array-layout.png)
*The 2 TX / 3 RX series-fed patch array as built in CSXCAD.*

![S11 of the array](../../public/images/simulation/array-s11.png)
*Array S11: −16 dB at 60.6 GHz.*

![Radiation pattern of the array at 60.65 GHz](../../public/images/simulation/array-directivity.png)
*Array directivity at 60.65 GHz.*

Compared the simulated radiation pattern against TI's measured data for
the board: good match.

![Simulated array pattern at 62 GHz](../../public/images/simulation/array-directivity-62ghz.png)
*Simulated pattern at 62 GHz…*

![TI measured azimuth radiation patterns](../../public/images/simulation/ti-measured-radiation-patterns.png)
*…versus TI's measured TX→RX azimuth patterns for the xWRL6432 board
(source: TI radar platform documentation).*

## Step 2: hardware replication

Rebuilt the bench in the simulator, ticking through:

- Reflector and wall above the antenna; observed the TX1 Gaussian pulse
  reflection on RX1/RX2/RX3, with visualization videos.
- Chirp emission and BPM MIMO, using the real chirp parameters
  (58 to 61.88 GHz sweep).

![FDTD scene: PCB with the array and a wall above it](../../public/images/simulation/fdtd-scene-wall.png)
*The FDTD scene: antenna PCB, reflecting wall above, and the mesh.*

![Port voltages: TX1 pulse and its echoes on all ports](../../public/images/simulation/gaussian-pulse-all-ports.png)
*TX1 emits the Gaussian pulse (black); the echo arrives on the RX ports
~2×10⁻¹⁰ s later.*

![Zoom on the received echo at the RX ports](../../public/images/simulation/gaussian-pulse-rx-zoom.png)
*Zoom on the RX ports: the wall echo received by RX1/RX2/RX3.*

Why a Gaussian pulse: a pulse centered on f = 0 Hz has no sinusoidal
component, while one centered on a nonzero carrier is a sinusoid inside a
Gaussian envelope — one shot excites the whole band of interest.

![Gaussian pulse in time and frequency domain](../../public/images/simulation/gaussian-pulse-time-frequency.png)
*Time domain vs frequency domain for baseband and carrier-centered
Gaussian pulses.*

The chirp uses the real hardware configuration:

![Chirp configuration parameters](../../public/images/simulation/chirp-parameters.png)
*The real chirp: 58 GHz start, 160 MHz/µs slope, 256 ADC samples,
24.3 µs ramp — ending at 61.88 GHz.*

### The trick that made it tractable

Full FDTD of one FMCW chirp is impossible: a 24.3 us chirp at 61.88 GHz
needs a ~1.6e-14 s time step, i.e. ~1.5 million steps, ~9.2 days per
simulation. Instead:

1. Excite each scene once with a Gaussian pulse and extract the full
   transfer function of the material stack: power vs frequency for each
   TX-RX pair (a 2D tensor: frequency x 6 channel pairs).
2. Multiply any excitation (the chirp) by that matrix.

![Sketch of the six transfer functions](../../public/images/simulation/transfer-function-concept.png)
*The idea: for a given material at a given distance and thickness, six
gain/phase transfer functions (TX1/TX2 × RX1/RX2/RX3) characterize the
scene completely.*

![Computed Bode diagram of the six transfer functions](../../public/images/simulation/transfer-functions-bode.png)
*The six transfer functions extracted from one Gaussian-pulse run: gain
and phase per TX–RX pair across the band.*

![Received chirps after multiplying by the transfer matrix](../../public/images/simulation/chirp-times-transfer.png)
*The 24.3 µs chirp pushed through the transfer matrix: received signal
envelopes for the TX1 and TX2 channels — no 9-day FDTD run needed.*

Sanity check on linearity: nonlinear material effects appear at MW/cm2;
we are at mW/cm2, so pure transfer functions are valid.

### Rest of the chain

- BPM decoding, TX/RX mixing, and the ADC sampler (256 samples, matching
  the real buffer).
- Range FFT (3 cm range bins), then Capon beamforming: matrix inversion,
  problem reformulation, and reconstruction of the 3D image, compared
  against real measured data.

![The six beat signals in the 256-sample ADC buffer](../../public/images/simulation/adc-buffer-256.png)
*The six mixed-down channels as they land in the 256-sample ADC buffer.*

![Range FFT output for the six virtual antennas](../../public/images/simulation/range-fft-output.png)
*Range FFT output per virtual antenna.*

![Capon beamforming output](../../public/images/simulation/capon-3d-image.png)
*Capon beamforming of the simulated scene (power vs azimuth/elevation for
one range bin).*

![Real measured heatmap from the radar](../../public/images/simulation/capon-real-measured.png)
*The same processing on real measured data, for comparison.*

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

![Casing model in front of the sensor](../../public/images/simulation/casing-model.png)
*The plastic casing modeled in front of the sensor: 2 mm wall.*

The debug trail in pictures:

![Capon output implying 11.7 mm RX-TX spacing](../../public/images/simulation/capon-spacing-11p7mm.png)
*Fringe spacing in the Capon output implies an apparent RX–TX spacing of
11.7 mm…*

![Capon output implying 10.8 mm RX-TX spacing](../../public/images/simulation/capon-spacing-10p8mm.png)
*…and here 10.8 mm — but the real board spacing is 11.8 mm. Something is
off.*

![Bode diagram of the TX1 - TX2 BPM mode](../../public/images/simulation/bode-tx1-minus-tx2.png)
*Bode diagram of the TX1 − TX2 BPM mode…*

![Bode diagram of the TX1 + TX2 BPM mode](../../public/images/simulation/bode-tx1-plus-tx2.png)
*…and of the TX1 + TX2 mode: the TX2 channels don't behave — because the
sim had only ever been excited from TX1.*

![Capon output with the correct 11.8 mm spacing](../../public/images/simulation/capon-spacing-11p8mm.png)
*After re-running the simulation with TX2 as the emitter: apparent
spacing 11.8 mm, matching the board.*

![Final Capon output after the fix](../../public/images/simulation/capon-after-fix.png)
*The fixed pipeline: a single clean reflection where it should be.*
