import numpy as np
import rasterio
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
from pathlib import Path


class PCAAnalyzer:
    def __init__(self, tile_name):
        self.tile_name = tile_name
        self.tile_dir = Path("data") / Path(tile_name).stem
    
    def run(self):
        with rasterio.open(self.tile_dir / "embeddings_tiled.tif") as src:
            embeddings = src.read()
            profile = src.profile
        
        h, w = embeddings.shape[1], embeddings.shape[2]
        embeddings_flat = embeddings.reshape(1024, -1).T
        
        pca = PCA(n_components=3)
        rgb = pca.fit_transform(embeddings_flat)
        
        rgb_image = rgb.reshape(h, w, 3)
        
        for i in range(3):
            pc = rgb_image[:, :, i]
            pc_min, pc_max = pc.min(), pc.max()
            rgb_image[:, :, i] = 255 * (pc - pc_min) / (pc_max - pc_min)
        
        rgb_image = rgb_image.astype(np.uint8)
        
        profile.update(count=3, dtype='uint8')
        with rasterio.open(self.tile_dir / "pca_rgb.tif", "w", **profile) as dst:
            for i in range(3):
                dst.write(rgb_image[:, :, i], i + 1)
        
        plt.figure(figsize=(10, 10))
        plt.imshow(rgb_image)
        plt.title("PCA RGB Visualization\nPC1=Red, PC2=Green, PC3=Blue")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(self.tile_dir / "pca_rgb.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Saved: {self.tile_dir / 'pca_rgb.tif'} and {self.tile_dir / 'pca_rgb.png'}")
        print(f"Explained variance: {pca.explained_variance_ratio_}")
