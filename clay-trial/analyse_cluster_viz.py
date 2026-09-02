import numpy as np
import rasterio
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
from pathlib import Path

#TILE_NAME = "AY30_1000_4448.tiff"
#TILE_NAME = "BA31_1000_4047.tiff"
TILE_NAME = "BA31_1000_4048.tiff"
tile_dir = Path("data") / Path(TILE_NAME).stem

# Read embeddings
with rasterio.open(tile_dir / "embeddings_tiled.tif") as src:
    embeddings = src.read()
    profile = src.profile

# Reshape to (n_pixels, 1024)
h, w = embeddings.shape[1], embeddings.shape[2]
embeddings_flat = embeddings.reshape(1024, -1).T

# KMeans clustering
clusters = KMeans(n_clusters=20).fit_predict(embeddings_flat)
cluster_map = clusters.reshape(h, w)

# Save
profile.update(count=1, dtype='uint8')
with rasterio.open(tile_dir / "clusters.tif", "w", **profile) as dst:
    dst.write(cluster_map.astype(np.uint8), 1)

# Display
plt.figure(figsize=(10, 10))
plt.imshow(cluster_map, cmap='tab20')
plt.colorbar(label='Cluster ID')
plt.title("KMeans Clustering (k=20)")
plt.axis('off')
plt.savefig(tile_dir / "clusters.png", dpi=150, bbox_inches='tight')
print(f"Saved: {tile_dir / 'clusters.tif'} and {tile_dir / 'clusters.png'}")
