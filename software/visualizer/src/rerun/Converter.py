import rerun as rr
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt


def convert(number=0):
    # Load the recording
    path = "recorded_data/rice_big_training2/nostone/data"
    suffix = ".rrd"
    input_path = path + str(number) + suffix
    recording = rr.dataframe.load_recording(input_path)

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
    output_path = path+str(number)+".npy"
    np.save(output_path, heatmaps)
    print("Saved!")
    return True



if __name__ == "__main__": 
    for i in range(4):
        convert(number=i)