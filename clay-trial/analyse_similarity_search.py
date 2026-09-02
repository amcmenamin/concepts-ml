import numpy as np
import rasterio
import matplotlib.pyplot as plt
from pathlib import Path

#TILE_NAME = "AY30_1000_4448.tiff"
#TILE_NAME = "BA31_1000_4047.tiff"
TILE_NAME = "BA31_1000_4048.tiff"
tile_dir = Path("data") / Path(TILE_NAME).stem

# Set the reference location here:
REF_ROW_COL = (18, 16)  # (row, col) or None
REF_LONLAT = None        # (lon, lat) or None

# Read embeddings
with rasterio.open(tile_dir / "embeddings_tiled.tif") as src:
    embeddings = src.read()
    profile = src.profile
    transform = src.transform

# Reshape to (n_pixels, 1024)
h, w = embeddings.shape[1], embeddings.shape[2]
embeddings_flat = embeddings.reshape(1024, -1).T

# Resolve reference pixel location
if REF_ROW_COL is not None:
    cy, cx = REF_ROW_COL
elif REF_LONLAT is not None:
    row, col = rasterio.transform.rowcol(transform, REF_LONLAT[0], REF_LONLAT[1])
    cy, cx = row, col
else:
    cy, cx = h // 2, w // 2

# Define reference area (3x3 pixels around the chosen location)
ref_pixels = embeddings[:, cy-1:cy+2, cx-1:cx+2].reshape(1024, -1).T
reference_embedding = ref_pixels.mean(0)

# Normalize for cosine similarity
embeddings_norm = embeddings_flat / np.linalg.norm(embeddings_flat, axis=1, keepdims=True)
reference_norm = reference_embedding / np.linalg.norm(reference_embedding)

# Compute similarity
similarity = embeddings_norm @ reference_norm
similarity_map = similarity.reshape(h, w)

# Save
profile.update(count=1, dtype='float32')
with rasterio.open(tile_dir / "similarity.tif", "w", **profile) as dst:
    dst.write(similarity_map.astype(np.float32), 1)

# Display
plt.figure(figsize=(10, 10))
plt.imshow(similarity_map, cmap='RdYlGn', vmin=0, vmax=1)
plt.colorbar(label='Cosine Similarity')
plt.title(f"Similarity to Reference (row={cy}, col={cx}, 3x3)")
plt.plot(cx, cy, 'r*', markersize=15, label='Reference')
plt.legend()
plt.axis('off')
plt.savefig(tile_dir / "similarity.png", dpi=150, bbox_inches='tight')
print(f"Saved: {tile_dir / 'similarity.tif'} and {tile_dir / 'similarity.png'}")
print(f"Reference location: ({cx}, {cy})")
