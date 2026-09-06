import numpy as np
import rasterio
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
from pathlib import Path


class PCAAnalyzer:
    def __init__(self, embedding_path):
        self.embedding_path = Path(embedding_path)
        self.output_dir = self.embedding_path.parent
    
    def run(self):
        with rasterio.open(self.embedding_path) as src:
            embeddings = src.read()
            profile = src.profile
        
        h, w = embeddings.shape[1], embeddings.shape[2]
        embeddings_flat = embeddings.reshape(embeddings.shape[0], -1).T
        
        pca = PCA(n_components=3)
        rgb = pca.fit_transform(embeddings_flat)
        
        rgb_image = rgb.reshape(h, w, 3)
        
        for i in range(3):
            pc = rgb_image[:, :, i]
            pc_min, pc_max = pc.min(), pc.max()
            rgb_image[:, :, i] = 255 * (pc - pc_min) / (pc_max - pc_min)
        
        rgb_image = rgb_image.astype(np.uint8)
        
        profile.update(count=3, dtype='uint8')
        with rasterio.open(self.output_dir / "pca_rgb.tif", "w", **profile) as dst:
            for i in range(3):
                dst.write(rgb_image[:, :, i], i + 1)
        
        plt.figure(figsize=(10, 10))
        plt.imshow(rgb_image)
        plt.title("PCA RGB Visualization\nPC1=Red, PC2=Green, PC3=Blue")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(self.output_dir / "pca_rgb.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Saved: {self.output_dir / 'pca_rgb.tif'} and {self.output_dir / 'pca_rgb.png'}")
        print(f"Explained variance: {pca.explained_variance_ratio_}")
