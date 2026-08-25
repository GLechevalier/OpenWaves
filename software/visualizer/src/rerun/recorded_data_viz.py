from pathlib import Path

import rerun as rr

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "rerun_recorded_data"

# Open the recording in the viewer
rr.init("replay", spawn=True)
rr.log_file_from_path(DATA_DIR / "plastic_sheet.rrd")
