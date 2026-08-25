import rerun as rr
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt


DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "rerun_recorded_data"


def convert(number=1):
    # Load the recording
    input_path = DATA_DIR / "house_test" / "rrd" / f"data_{number}.rrd"
    recording = rr.dataframe.load_recording(str(input_path))

    # Get the heatmap data
    view = recording.view(index="timestamp", contents="radar/heatmap_3d")
    table = view.select().read_all()

    # Get the tensor column (note the leading slash)
    tensor_column = table.column("/radar/heatmap_3d:Tensor:data")

    # Extract numpy arrays
    heatmaps = []
    for batch in tensor_column:
        for item in batch:
            if item is not None:
                # Get shape and buffer directly
                shape = item["shape"].as_py()  # [10, 32, 16]
                buffer = item["buffer"].as_py()  # list of floats
                
                # Convert to numpy and reshape
                arr = np.array(buffer, dtype=np.float32).reshape(shape)
                heatmaps.append(arr)

    heatmaps = np.array(heatmaps)
    print(f"Shape: {heatmaps.shape}")  # Should be (num_frames, 10, 32, 16)

    # Save
    output_path = DATA_DIR / "house_test" / "npy" / f"data_{number}.npy"
    np.save(output_path, heatmaps)
    print("Saved!")
    return True



if __name__ == "__main__":
    for i in range(1, 11):
        convert(number=i)