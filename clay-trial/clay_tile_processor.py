import torch
import numpy as np
import rasterio
from rasterio.windows import Window
from claymodel.module import ClayMAEModule
import gc
from pathlib import Path
from box import Box
import yaml


class ClayTileProcessor:
    def __init__(self, checkpoint_path="clay-v1.5.ckpt", metadata_path="configs/metadata.yaml", 
                 tile_size=256, embedding_mode="patches"):
        self.tile_size = tile_size
        self.embedding_mode = embedding_mode
        self.device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        
        # Load model
        self.model = ClayMAEModule.load_from_checkpoint(
            checkpoint_path,
            model_size="large",
            metadata_path=metadata_path,
            dolls=[16, 32, 64, 128, 256, 768, 1024],
            doll_weights=[1, 1, 1, 1, 1, 1, 1],
            mask_ratio=0.0,
            shuffle=False,
            map_location=self.device
        )
        self.model.eval()
        self.model = self.model.to(self.device)
        
        self.metadata = Box(yaml.safe_load(open(metadata_path)))
        print(f"Model loaded on {self.device}")
    
    def _get_band_config(self, num_bands):
        """Get platform and band configuration based on number of bands."""
        if num_bands == 3:
            platform = "linz-rgb"
            band_names = ['red', 'green', 'blue']
        elif num_bands == 4:
            platform = "linz-nir"
            band_names = ['red', 'green', 'blue', 'nir']
        else:
            raise ValueError(f"Unsupported number of bands: {num_bands}")
        
        mean = [self.metadata[platform].bands.mean[band] for band in band_names]
        std = [self.metadata[platform].bands.std[band] for band in band_names]
        waves = [self.metadata[platform].bands.wavelength[band] for band in band_names]
        gsd = self.metadata[platform].gsd
        
        return platform, band_names, mean, std, waves, gsd
    
    def _process_tile(self, pixels, lat, lon, gsd, waves, platform):
        """Process a single 256x256 tile through the model."""
        week = 1 * 2 * np.pi / 52
        hour = 12 * 2 * np.pi / 24
        lat_rad = lat * np.pi / 180
        lon_rad = lon * np.pi / 180
        
        datacube = {
            "platform": platform,
            "time": torch.tensor([[np.sin(week), np.cos(week), np.sin(hour), np.cos(hour)]], 
                                dtype=torch.float32, device=self.device),
            "latlon": torch.tensor([[np.sin(lat_rad), np.cos(lat_rad), np.sin(lon_rad), np.cos(lon_rad)]], 
                                  dtype=torch.float32, device=self.device),
            "pixels": pixels.unsqueeze(0).to(self.device),
            "gsd": torch.tensor(gsd, dtype=torch.float32, device=self.device),
            "waves": torch.tensor(waves, dtype=torch.float32, device=self.device),
        }
        
        with torch.no_grad():
            unmsk_patch, _, _, _ = self.model.model.encoder(datacube)
            if self.embedding_mode == "cls":
                embeddings = unmsk_patch[:, 0:1, :].cpu().numpy()
            else:
                embeddings = unmsk_patch[:, 1:, :].cpu().numpy()
        
        del datacube, unmsk_patch
        torch.cuda.empty_cache()
        return embeddings
    
    def process_image(self, image_path, output_dir=None):
        """Process an entire image by tiling."""
        tif_path = Path(image_path)
        
        if output_dir is None:
            output_dir = Path("data") / tif_path.stem
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with rasterio.open(tif_path) as src:
            num_bands = src.count
            height, width = src.height, src.width
            
            print(f"\nProcessing: {tif_path.name}")
            print(f"Image size: {width}x{height}, Bands: {num_bands}")
            
            # Get band configuration
            platform, band_names, mean, std, waves, gsd = self._get_band_config(num_bands)
            print(f"Platform: {platform}, Bands: {band_names}")
            
            n_tiles_x = width // self.tile_size
            n_tiles_y = height // self.tile_size
            total_tiles = n_tiles_x * n_tiles_y
            print(f"Processing {n_tiles_x}x{n_tiles_y} = {total_tiles} tiles")
            print(f"Embedding mode: {self.embedding_mode}")
            
            embeddings_map = None
            embedding_dim = None
            patches_per_tile = None
            
            tile_count = 0
            for ty in range(n_tiles_y):
                for tx in range(n_tiles_x):
                    tile_count += 1
                    if tile_count % 10 == 0:
                        print(f"Processing tile {tile_count}/{total_tiles}")
                    
                    # Read tile
                    window = Window(tx * self.tile_size, ty * self.tile_size, 
                                  self.tile_size, self.tile_size)
                    tile_data = src.read(list(range(1, num_bands + 1)), window=window).astype(np.float32)
                    
                    # Normalize
                    tile_tensor = torch.from_numpy(tile_data)
                    for i, (m, s) in enumerate(zip(mean, std)):
                        tile_tensor[i] = (tile_tensor[i] - m) / s
                    
                    # Get center lat/lon
                    center_x = (tx + 0.5) * self.tile_size
                    center_y = (ty + 0.5) * self.tile_size
                    lon, lat = src.xy(center_y, center_x)
                    
                    # Process tile
                    embeddings = self._process_tile(tile_tensor, lat, lon, gsd, waves, platform)
                    
                    # Initialize embeddings_map on first tile
                    if embeddings_map is None:
                        embedding_dim = embeddings.shape[2]
                        patches_per_tile = 1 if self.embedding_mode == "cls" else int(embeddings.shape[1] ** 0.5)
                        embeddings_map = np.zeros((n_tiles_y * patches_per_tile, 
                                                  n_tiles_x * patches_per_tile, 
                                                  embedding_dim), dtype=np.float32)
                        print(f"Embedding dimension: {embedding_dim}")
                        print(f"Patches per tile: {patches_per_tile}x{patches_per_tile}")
                    
                    # Place embeddings
                    if self.embedding_mode == "cls":
                        embeddings_map[ty, tx] = embeddings[0, 0]
                    else:
                        patches_2d = embeddings[0].reshape(patches_per_tile, patches_per_tile, embedding_dim)
                        embeddings_map[ty*patches_per_tile:(ty+1)*patches_per_tile,
                                     tx*patches_per_tile:(tx+1)*patches_per_tile] = patches_2d
                    
                    gc.collect()
            
            # Prepare output profile
            output_profile = src.profile.copy()
            pixel_scale = self.tile_size // patches_per_tile if self.embedding_mode == "patches" else self.tile_size
            output_profile.update({
                'count': embedding_dim,
                'dtype': 'float32',
                'width': n_tiles_x * patches_per_tile,
                'height': n_tiles_y * patches_per_tile,
                'transform': src.transform * src.transform.scale(pixel_scale, pixel_scale)
            })
        
        print(f"All tiles processed. Embeddings shape: {embeddings_map.shape}")
        
        output_path = output_dir / "embeddings_tiled.tif"
        with rasterio.open(output_path, "w", **output_profile) as dst:
            for i in range(embedding_dim):
                dst.write(embeddings_map[:, :, i], i + 1)
        
        print(f"Embeddings saved to {output_path}")
        return output_path


if __name__ == "__main__":
    processor = ClayTileProcessor(embedding_mode="patches")
    processor.process_image("data/BA31_10000_0405.tiff")
