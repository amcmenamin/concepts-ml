import numpy as np
import rasterio
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
from pathlib import Path


class ClusterAnalyzer:
    def __init__(self, tile_name, n_clusters=20):
        self.tile_name = tile_name
        self.tile_dir = Path("data") / Path(tile_name).stem
        self.n_clusters = n_clusters
    
    def run(self):
        with rasterio.open(self.tile_dir / "embeddings_tiled.tif") as src:
            embeddings = src.read()
            profile = src.profile
        
        h, w = embeddings.shape[1], embeddings.shape[2]
        embeddings_flat = embeddings.reshape(1024, -1).T
        
        clusters = KMeans(n_clusters=self.n_clusters).fit_predict(embeddings_flat)
        cluster_map = clusters.reshape(h, w)
        
        profile.update(count=1, dtype='uint8')
        with rasterio.open(self.tile_dir / "clusters.tif", "w", **profile) as dst:
            dst.write(cluster_map.astype(np.uint8), 1)
        
        plt.figure(figsize=(10, 10))
        plt.imshow(cluster_map, cmap='tab20')
        plt.colorbar(label='Cluster ID')
        plt.title(f"KMeans Clustering (k={self.n_clusters})")
        plt.axis('off')
        plt.savefig(self.tile_dir / "clusters.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Saved: {self.tile_dir / 'clusters.tif'} and {self.tile_dir / 'clusters.png'}")
