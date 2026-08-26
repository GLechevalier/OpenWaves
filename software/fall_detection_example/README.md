# Fall detection

Real-time fall detection on a TI IWRL6432BOOST: the radar's point cloud +
tracker output feeds an XGBoost/CNN late-fusion classifier (tabular
features + micro-Doppler spectrogram), visualized live in
[Rerun](https://rerun.io).

**Firmware note**: this demo targets TI's stock **Motion and Presence
Detection** firmware (the `.cfg` files here use its tracker commands), not
the material-classification firmware bundled with `openwaves flash`. See
[docs/cli-commands.md](../../docs/cli-commands.md#two-firmwares-two-command-sets).

## Setup

```bash
pip install -e software/pyopenwaves[viz,ml]     # from the repo root
pip install torch json_fix
```

All scripts assume this directory as the working directory:

```bash
cd software/fall_detection_example
```

## Run

```bash
# Live fall detection (models included in models/), phone UI on :8766
python src/examples/fall_detector_example.py --cfg cfg/Tracking_MidBw.cfg

# Just the live point cloud in Rerun
python src/real_time/radar_point_cloud_viz.py

# Two radars fused into one room view (edit the COM ports at the top)
python src/real_time/dual_radar_room_viz.py

# Estimate the radar's mounting height from the floor plane
python src/examples/estimate_radar_height.py
```

## Pose estimation (SPiKE)

Three optional scripts (`src/async/Itop_viz.py`,
`src/real_time/itop_viz_inference_rt.py`,
`src/real_time/radar_SPiKE_model_inference_rt.py`) run skeleton estimation
with [SPiKE](https://github.com/iballester/SPiKE) — 3D human pose from point
cloud sequences. They need a local SPiKE workspace, pointed to by the
`SPIKE_DIR` environment variable:

```
$SPIKE_DIR/
  SPiKE/                  # git clone https://github.com/iballester/SPiKE
    experiments/ITOP-SIDE/1/log/best_model.pth   # trained checkpoint (train or download per SPiKE's README)
  dataset_SPiKE/
    test/                 # ITOP test split preprocessed as {frame_id}.npz point clouds
    test_labels.h5        # ITOP ground-truth joints
```

```bash
# e.g. (PowerShell)  $env:SPIKE_DIR = "D:\path\to\spike_workspace"
#      (bash)        export SPIKE_DIR=~/spike_workspace
python src/real_time/radar_SPiKE_model_inference_rt.py     # live radar → skeleton
```

The rest of the fall detection demo does not need SPiKE.

## Train your own

```bash
python src/ML/radar_data_collector.py      # record labeled sessions (phone marker on :8765)
python src/ML/diagnose.py                  # dataset QA / relabeling
python src/ML/train_fall_detector.py       # XGBoost + CNN + fusion weights -> models/
```

Recorded sessions (subject S01, falls + daily activities) are included
under `../data/fall_detection/data/sessions/`.

## Layout

- `cfg/` — radar configurations (see [docs/cli-commands.md](../../docs/cli-commands.md))
- `src/real_time/radar_utils/RadarParser.py` — serial glue (thin shim over the `openwaves` package)
- `src/data_processors/` — height estimation, posture detection, fall detector
- `src/ML/` — data collection, training, diagnostics
- `models/` — pretrained XGBoost/CNN/fusion/posture models
