import numpy as np
import rasterio
import umap
import matplotlib.pyplot as plt
from pathlib import Path


class UMAPAnalyzer:
    def __init__(self, embedding_path, n_neighbors=15, min_dist=0.1):
        self.embedding_path = Path(embedding_path)
        self.output_dir = self.embedding_path.parent
        self.n_neighbors = n_neighbors
        self.min_dist = min_dist
    
    def run(self):
        with rasterio.open(self.embedding_path) as src:
            embeddings = src.read()
            profile = src.profile
        
        h, w = embeddings.shape[1], embeddings.shape[2]
        embeddings_flat = embeddings.reshape(embeddings.shape[0], -1).T
        
        reducer = umap.UMAP(n_components=3, n_neighbors=self.n_neighbors, min_dist=self.min_dist)
        xyz = reducer.fit_transform(embeddings_flat)
        
        rgb_image = xyz.reshape(h, w, 3)
        for i in range(3):
            comp = rgb_image[:, :, i]
            rgb_image[:, :, i] = 255 * (comp - comp.min()) / (comp.max() - comp.min())
        
        profile.update(count=3, dtype='uint8')
        with rasterio.open(self.output_dir / "umap_rgb.tif", "w", **profile) as dst:
            for i in range(3):
                dst.write(rgb_image[:, :, i].astype(np.uint8), i + 1)
        
        plt.figure(figsize=(10, 10))
        plt.imshow(rgb_image.astype(np.uint8))
        plt.title("UMAP RGB Visualization")
        plt.axis('off')
        plt.savefig(self.output_dir / "umap_rgb.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Saved: {self.output_dir / 'umap_rgb.tif'} and {self.output_dir / 'umap_rgb.png'}")
