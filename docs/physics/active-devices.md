# Active devices

Course notes on semiconductors and the active devices used in RF systems.
Three parts: semiconductor physics, device technologies for wireless, and
what an active device needs to work as a power amplifier.

## Semiconductors in a nutshell

A semiconductor sits between a conductor and an insulator, and the whole
point is that its conductivity is controllable: by temperature, by doping,
or by an applied electric field. Silicon covers ~95% of modern electronics;
GaAs, SiC and GaN cover the high-frequency and power niches.

- **Energy bands**: electrons live in a valence band, conduction happens in
  a conduction band, and the gap between them decides everything. Insulator
  gap > 5 eV, semiconductor gap 0.5-3 eV (Si: ~1.1 eV), conductor bands
  overlap.
- **Carriers**: thermal agitation frees electrons (e-) and leaves holes (h+)
  behind. Pure Si has only ~10^10 carriers/cm3, which is why doping exists.
- **N-type**: dope with a 5-valence-electron atom (P, As, Sb), each dopant
  donates a free electron. Majority carriers: electrons.
- **P-type**: dope with a 3-valence-electron atom (B, Al, Ga), each dopant
  creates a hole. Majority carriers: holes.

### The PN junction

Put P and N in contact and carriers diffuse across, leaving a depletion
region with a built-in field. That gives the one-way valve every component
is built on:

- **Forward bias** (P to +): barrier drops, majority carriers cross, current
  flows.
- **Reverse bias** (P to -): barrier grows, only leakage current flows.

Diode equation: `I = Is * (e^(V/nVt) - 1)` with `Is ~ 1e-12 A`,
`Vt ~ 26 mV` at 25 C, `n` between 1 and 2.

From this one building block: diodes (rectification, LEDs), bipolar
transistors (two junctions, current-controlled amplification), MOSFETs
(field-controlled channel, no gate current), and integrated circuits.

## Unipolar vs bipolar: FETs and BJTs

Two transport mechanisms, two device families:

| Aspect | FET (unipolar) | BJT (bipolar) |
|---|---|---|
| Control | Voltage on the gate | Current into the base |
| Input impedance | Very high (MΩ+) | Low (a few kΩ) |
| Carriers | Majority only | Electrons and holes |
| Gain figure | Transconductance g_m | Current gain β |
| Power density | Lower | Higher |
| RF noise | Thermal, lower: good for LNAs | Shot noise, higher |
| Fabrication | Simpler | More complex |

Silicon devices win on cost, volume and mature manufacturing. Compound
semiconductors win on intrinsic material performance at high frequency
(MMICs), at the price of a more limited manufacturing base.

## Material systems

- **Si / Ge**: cheap, great thermal conductivity (easy cooling), but slow
  electron mobility and no semi-insulating substrate, which adds cost.
- **GaAs**: higher mobility than Si, the MMIC workhorse for decades, used in
  high-sensitivity receivers. Major drawback: poor thermal dissipation.
- **GaN**: dominates the power amplifier market. Fastest drift velocity,
  wide bandgap so high breakdown field, low thermal resistance: the right
  answer for high-power RF.
- **InP**: the fastest transistors of all, used in optoelectronics, thermal
  handling is problematic. A possible GaAs successor.

## Power amplification requirement

To build an amplifier out of an active device, the device must actually
have the amplifier properties (gain, linearity, efficiency, breakdown
margin) at the target frequency. Both bipolar transistors and MOSFETs
qualify; the material system above decides how much power and at what
frequency.
