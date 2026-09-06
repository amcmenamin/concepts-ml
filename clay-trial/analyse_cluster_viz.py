import numpy as np
import rasterio
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
from pathlib import Path


class ClusterAnalyzer:
    def __init__(self, embedding_path, n_clusters=20):
        self.embedding_path = Path(embedding_path)
        self.output_dir = self.embedding_path.parent
        self.n_clusters = n_clusters
    
    def run(self):
        with rasterio.open(self.embedding_path) as src:
            embeddings = src.read()
            profile = src.profile
        
        h, w = embeddings.shape[1], embeddings.shape[2]
        embeddings_flat = embeddings.reshape(embeddings.shape[0], -1).T
        
        clusters = KMeans(n_clusters=self.n_clusters).fit_predict(embeddings_flat)
        cluster_map = clusters.reshape(h, w)
        
        profile.update(count=1, dtype='uint8')
        with rasterio.open(self.output_dir / "clusters.tif", "w", **profile) as dst:
            dst.write(cluster_map.astype(np.uint8), 1)
        
        plt.figure(figsize=(10, 10))
        plt.imshow(cluster_map, cmap='tab20')
        plt.colorbar(label='Cluster ID')
        plt.title(f"KMeans Clustering (k={self.n_clusters})")
        plt.axis('off')
        plt.savefig(self.output_dir / "clusters.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Saved: {self.output_dir / 'clusters.tif'} and {self.output_dir / 'clusters.png'}")
