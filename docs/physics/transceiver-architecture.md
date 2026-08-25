# Transceiver architecture

Course notes on why RF receivers are built the way they are. The punchline:
everything is a variation on the heterodyne receiver, and the design is a
constant fight between noise, gain, filtering and the image problem.

## Prerequisites

- **Friis formula**: in a cascaded RF chain the first stage dominates the
  total noise figure. That is the whole reason the LNA comes first: get gain
  early and everything after it matters less for SNR.
- **Band vs channel**: a band is a chunk of spectrum (UHF TV: 470-860 MHz),
  a channel is a slice inside it (~8 MHz for TV). You filter the band with
  hardware, then select the channel later.

## What a receiver has to do

1. **Amplify**: antennas deliver microvolts, ADCs want millivolts, so you
   need lots of gain and a high dynamic range.
2. **Variable gain**: high gain for far transmitters, low gain for near
   ones. A VGA at RF is really hard (bandwidth and variable gain at once),
   another argument for downconverting first.
3. **Downconvert**: power consumption scales with operating frequency, so
   you mix the RF signal down to baseband/IF as early as possible. The
   popular arrangement is LNA then mixer, because Friis says the LNA must
   come first.
4. **Filter**: the most important requirement. Antennas pick up everything;
   adjacent channels must go. A band-pass filter with the required Q is
   expensive, so in practice you band-filter in hardware and channel-select
   after downconversion.

## The heterodyne receiver

Mix the RF input with a local oscillator (LO) chosen below the RF band; the
mixer output at `f_RF - f_LO` is the intermediate frequency (IF), much lower
and much cheaper to process.

### The image problem

Two different RF frequencies produce the same IF: `f_LO + f_IF` and
`f_LO - f_IF` both land on `f_IF` after mixing. The unwanted one is the
image, sitting at `f_IM = 2*f_LO - f_input`, i.e. `2*f_IF` away from the
signal. It must be removed with an image-reject filter before the mixer.

The catch: image rejection and channel selection pull the IF in opposite
directions, and one filter physically cannot do both well. That trade-off
is what differentiates receiver architectures.

Impulse radio receivers push this to the extreme: every component needs a
huge frequency range.

## The blocks worth designing

LNA, mixer, power amplifier, and the PLL/oscillator.

### PLL

A phase-locked loop generates the LO. Classic structure:

- phase frequency detector (PFD),
- loop filter,
- voltage-controlled oscillator (VCO),
- optional frequency divider in the feedback path.

Also available as a single integrated circuit.
