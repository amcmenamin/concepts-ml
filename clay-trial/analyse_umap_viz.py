import numpy as np
import rasterio
import umap
import matplotlib.pyplot as plt
from pathlib import Path

#TILE_NAME = "AY30_1000_4448.tiff"
TILE_NAME = "BA31_1000_4047.tiff"
#TILE_NAME = "BA31_1000_4048.tiff"
tile_dir = Path("data") / Path(TILE_NAME).stem

# Read embeddings
with rasterio.open(tile_dir / "embeddings_tiled.tif") as src:
    embeddings = src.read()
    profile = src.profile

# Reshape to (n_pixels, 1024)
h, w = embeddings.shape[1], embeddings.shape[2]
embeddings_flat = embeddings.reshape(1024, -1).T

# UMAP to 3 components
reducer = umap.UMAP(n_components=3, n_neighbors=15, min_dist=0.1)
xyz = reducer.fit_transform(embeddings_flat)

# Reshape and stretch to 0-255
rgb_image = xyz.reshape(h, w, 3)
for i in range(3):
    comp = rgb_image[:, :, i]
    rgb_image[:, :, i] = 255 * (comp - comp.min()) / (comp.max() - comp.min())

# Save and display
profile.update(count=3, dtype='uint8')
with rasterio.open(tile_dir / "umap_rgb.tif", "w", **profile) as dst:
    for i in range(3):
        dst.write(rgb_image[:, :, i].astype(np.uint8), i + 1)

plt.figure(figsize=(10, 10))
plt.imshow(rgb_image.astype(np.uint8))
plt.title("UMAP RGB Visualization")
plt.axis('off')
plt.savefig(tile_dir / "umap_rgb.png", dpi=150, bbox_inches='tight')
print(f"Saved: {tile_dir / 'umap_rgb.tif'} and {tile_dir / 'umap_rgb.png'}")
