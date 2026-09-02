import numpy as np
import rasterio
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
from pathlib import Path

#TILE_NAME = "AY30_1000_4448.tiff"
#TILE_NAME = "BA31_1000_4047.tiff"
TILE_NAME = "BA31_1000_4048.tiff"
tile_dir = Path("data") / Path(TILE_NAME).stem

# Read embeddings
with rasterio.open(tile_dir / "embeddings_tiled.tif") as src:
    embeddings = src.read()  # (1024, height, width)
    profile = src.profile

# Reshape to (n_pixels, 1024)
h, w = embeddings.shape[1], embeddings.shape[2]
embeddings_flat = embeddings.reshape(1024, -1).T

# PCA to 3 components
pca = PCA(n_components=3)
rgb = pca.fit_transform(embeddings_flat)  # (n_pixels, 3)

# Reshape back to image
rgb_image = rgb.reshape(h, w, 3)

# Stretch to 0-255
for i in range(3):
    pc = rgb_image[:, :, i]
    pc_min, pc_max = pc.min(), pc.max()
    rgb_image[:, :, i] = 255 * (pc - pc_min) / (pc_max - pc_min)

rgb_image = rgb_image.astype(np.uint8)

# Save as GeoTIFF
profile.update(count=3, dtype='uint8')
with rasterio.open(tile_dir / "pca_rgb.tif", "w", **profile) as dst:
    for i in range(3):
        dst.write(rgb_image[:, :, i], i + 1)

# Display
plt.figure(figsize=(10, 10))
plt.imshow(rgb_image)
plt.title("PCA RGB Visualization\nPC1=Red, PC2=Green, PC3=Blue")
plt.axis('off')
plt.tight_layout()
plt.savefig(tile_dir / "pca_rgb.png", dpi=150, bbox_inches='tight')
print(f"Saved: {tile_dir / 'pca_rgb.tif'} and {tile_dir / 'pca_rgb.png'}")
print(f"Explained variance: {pca.explained_variance_ratio_}")
