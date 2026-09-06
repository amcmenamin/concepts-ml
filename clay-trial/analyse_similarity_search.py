import numpy as np
import rasterio
import matplotlib.pyplot as plt
from pathlib import Path


class SimilarityAnalyzer:
    def __init__(self, embedding_path, ref_row_col=None, ref_lonlat=None):
        self.embedding_path = Path(embedding_path)
        self.output_dir = self.embedding_path.parent
        self.ref_row_col = ref_row_col
        self.ref_lonlat = ref_lonlat
    
    def run(self):
        with rasterio.open(self.embedding_path) as src:
            embeddings = src.read()
            profile = src.profile
            transform = src.transform
        
        h, w = embeddings.shape[1], embeddings.shape[2]
        embedding_dimension = embeddings.shape[0]
        embeddings_flat = embeddings.reshape(embedding_dimension, -1).T
        
        if self.ref_row_col is not None:
            cy, cx = self.ref_row_col
        elif self.ref_lonlat is not None:
            row, col = rasterio.transform.rowcol(transform, self.ref_lonlat[0], self.ref_lonlat[1])
            cy, cx = row, col
        else:
            cy, cx = h // 2, w // 2
        
        ref_pixels = embeddings[:, cy-1:cy+2, cx-1:cx+2].reshape(embedding_dimension, -1).T
        reference_embedding = ref_pixels.mean(0)
        
        embeddings_norm = embeddings_flat / np.linalg.norm(embeddings_flat, axis=1, keepdims=True)
        reference_norm = reference_embedding / np.linalg.norm(reference_embedding)
        
        similarity = embeddings_norm @ reference_norm
        similarity_map = similarity.reshape(h, w)
        
        profile.update(count=1, dtype='float32')
        with rasterio.open(self.output_dir / "similarity.tif", "w", **profile) as dst:
            dst.write(similarity_map.astype(np.float32), 1)
        
        plt.figure(figsize=(10, 10))
        plt.imshow(similarity_map, cmap='RdYlGn', vmin=0, vmax=1)
        plt.colorbar(label='Cosine Similarity')
        plt.title(f"Similarity to Reference (row={cy}, col={cx}, 3x3)")
        plt.plot(cx, cy, 'r*', markersize=15, label='Reference')
        plt.legend()
        plt.axis('off')
        plt.savefig(self.output_dir / "similarity.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Saved: {self.output_dir / 'similarity.tif'} and {self.output_dir / 'similarity.png'}")
        print(f"Reference location: ({cx}, {cy})")
