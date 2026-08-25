import rerun as rr

# Open the recording in the viewer
rr.init("replay", spawn=True)
rr.log_file_from_path("recorded_data/plastic_sheet.rrd")