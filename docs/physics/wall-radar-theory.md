# Wall radar theory

The physics behind analyzing a wall with radar: send an electromagnetic
wave into the wall, measure what comes back. Phase shift gives you where
the interfaces are; reflected intensity gives you what the material is.

## Propagation and distance

The wave travels through a material at `v = c / sqrt(εr * μr)`. A round
trip to an interface at depth d takes `t = 2d * sqrt(εr * μr) / c`, which
shows up as a phase shift:

```
Δφ = 4π f d sqrt(εr μr) / c   →   d = c Δφ / (4π f sqrt(εr μr))
```

Practical notes:

- Phase must be measured to better than ~1 degree for centimeter
  resolution.
- You need a rough εr estimate to get a first distance estimate.
- Depth resolution is bandwidth-limited: `Δd ≈ c / (2 B sqrt(εr))`.

## Material identification by reflection

At the air-material interface the reflection coefficient is
`R = (Z1 - Z0) / (Z1 + Z0)` with `Z0 ≈ 377 Ω` (air) and
`Z1 = sqrt(μ0 μr / ε0 εr)`. The measured intensity is `|R|²`, and each
material has a signature:

| Material | εr | μr | \|R\|² approx |
|---|---|---|---|
| Air | 1 | 1 | 0 |
| Dry wood | 2-4 | 1 | 0.1-0.3 |
| Dry concrete | 4-8 | 1 | 0.3-0.5 |
| Brick | 4-6 | 1 | 0.3-0.4 |
| Steel | inf | 1000 | ~1 |
| Water | 81 | 1 | 0.8 |

## Frequency sweeping helps

εr and μr are complex and frequency-dependent (dielectric relaxation,
conductivity, magnetic resonances), so sweeping frequency turns a single
reflection number into a spectrum. That enriches the signature, separates
materials that look alike at one frequency, and averages out measurement
errors.

## Choosing the frequency range

- **Low (100 MHz - 1 GHz)**: penetrates well, low attenuation, but poor
  spatial resolution and big antennas.
- **High (1-10 GHz)**: excellent resolution, compact antennas, precise
  phase, but strong attenuation, limited penetration, and sensitivity to
  surface roughness.
- Skin depth sets the usable thickness: analyze at most ~3δ where
  `δ = c / (2πf sqrt(ε'r μ'r) sqrt(1 + (ε"r/ε'r)²))`.

## Why FMCW

Emit a linearly swept chirp, mix the echo with the transmitted signal, FFT
the beat signal. You get distance and amplitude simultaneously, good noise
immunity, no TX/RX synchronization headache, and one antenna can do both
jobs. Processing chain: I/Q sampling of the beat signal, FFT, peak
detection for interfaces, spectral analysis for material signatures.

## Limits and mitigations

- **Physics**: multiple reflections between parallel interfaces, composite
  walls (rebar, insulation), rough surfaces scattering non-specularly,
  antenna-wall coupling.
- **Environment**: humidity changes electrical properties drastically;
  temperature and contamination (salts, metal) also shift εr and σ.
- **Fixes**: calibration on reference materials, adaptive compensation,
  multi-frequency redundancy, and pattern recognition (ML) for the complex
  cases.

## Expected performance

- Resolution: 1-2 cm optimal (2-10 GHz band), 3-5 cm as the practical
  penetration/resolution compromise.
- Depth: 20-30 cm in light walls (wood, drywall), 10-20 cm in heavy walls
  (concrete, brick), surface only for metal.
- Identification: >95% on homogeneous materials, 80-90% on composites,
  70-85% in degraded conditions.

Detailed specs and implementation are Intramap confidential and not part
of this document.

Sources: [60 GHz radar material classification with a CNN](https://www.researchgate.net/publication/336086706_Material_Classification_using_60-GHz_Radar_and_Deep_Convolutional_Neural_Network),
[concrete characterization with EM waves (PDF, French)](http://www.bv.transports.gouv.qc.ca/mono/0981418/05_Caracterisation_beton_ondes_electromagnetiques.pdf).
