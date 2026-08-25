import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from scipy.stats import entropy
import matplotlib.pyplot as plt
import os
import sys
import pandas as pd


sys.path.append(os.getcwd())

DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "data", "rerun_recorded_data"
)

# Load and combine all batches (house_test: 1-5 = plafonds, 6-10 = murs)
files = [os.path.join(DATA_DIR, "house_test", "npy", f"data_{i}.npy") for i in range(1, 11)]
data = np.concatenate([np.load(f) for f in files], axis=0)

# Flatten each sample: (N, 10, 32*16) = (N, 5120)
n_samples = data.shape[0]
data_flat = data.reshape(n_samples, -1)
print(data_flat.shape)

# Normalize
scaler = StandardScaler()
data_scaled = scaler.fit_transform(data_flat)

# Optional: Reduce dimensionality first
pca = PCA(n_components=10)  # Adjust based on variance explained
data_reduced = pca.fit_transform(data_scaled)
print(f"Variance explained: {pca.explained_variance_ratio_.sum():.2%}")

# K-Means clustering
kmeans_res = {}
for n_clusters in range(2,5):
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(data_reduced)
    
    cluster_counts = np.bincount(labels)
    cluster_probs = cluster_counts / cluster_counts.sum()

    # Calculate entropy (base 2 for bits, or natural log by default)
    ent = entropy(cluster_probs, base=2)

    kmeans_res[n_clusters] ={"bincount": np.bincount(labels), "entropy":ent}

print(f"Cluster distribution: {kmeans_res}")

# Track which file and position each sample came from
sample_info = []
sample_idx = 0

for file_idx, f in enumerate(files):
    file_data = np.load(f)
    for pos in range(len(file_data)):
        sample_info.append({
            'sample_idx': sample_idx,
            'file': f,
            'file_idx': file_idx,
            'position_in_file': pos,
            'cluster': labels[sample_idx]
        })
        sample_idx += 1

df = pd.DataFrame(sample_info)
print(df.head(20))

# Now you can query easily
print("\n--- Samples in Cluster 2 ---")
print(df[df['cluster'] == 2])

# Count samples per file per cluster
print("\n--- Cluster distribution by file ---")
print(pd.crosstab(df['file_idx'], df['cluster']))

