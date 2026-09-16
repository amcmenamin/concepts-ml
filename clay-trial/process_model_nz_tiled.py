import torch
import numpy as np
import rasterio
from rasterio.windows import Window
from claymodel.module import ClayMAEModule
import gc
from pathlib import Path

# Global tile configuration
#TILE_NAME = "AY30_1000_4448.tiff"
#TILE_NAME = "BA31_1000_4047.tiff"
#TILE_NAME = "BA31_1000_4048.tiff"
TILE_NAME = "BA31_10000_0405.tiff"

# Embedding mode: "cls" for CLS token (coarse), "patches" for all patches (fine)
EMBEDDING_MODE = "patches"  # or "cls"

def process_tile(model, pixels, lat, lon, gsd, waves, platform, device, mode="patches"):
    """Process a single 256x256 tile through the model."""
    # Normalize timestamp for single image (no temporal dimension)
    week = 1 * 2 * np.pi / 52  # Default week 1
    hour = 12 * 2 * np.pi / 24  # Default noon
    
    # Normalize lat/lon
    lat_rad = lat * np.pi / 180
    lon_rad = lon * np.pi / 180
    
    datacube = {
        "platform": platform,
        "time": torch.tensor([[np.sin(week), np.cos(week), np.sin(hour), np.cos(hour)]], dtype=torch.float32, device=device),
        "latlon": torch.tensor([[np.sin(lat_rad), np.cos(lat_rad), np.sin(lon_rad), np.cos(lon_rad)]], dtype=torch.float32, device=device),
        "pixels": pixels.unsqueeze(0).to(device),
        "gsd": torch.tensor(gsd, dtype=torch.float32, device=device),
        "waves": torch.tensor(waves, dtype=torch.float32, device=device),
    }
    
    #print(f"datacube: {datacube}")
    
    with torch.no_grad():
        unmsk_patch, _, _, _ = model.model.encoder(datacube)
        if mode == "cls":
            # CLS token only (global summary)
            embeddings = unmsk_patch[:, 0:1, :].cpu().numpy()  # (1, 1, 1024)
        else:
            # All patch embeddings (skip CLS token)
            embeddings = unmsk_patch[:, 1:, :].cpu().numpy()  # (1, 256, 1024)
    
    del datacube, unmsk_patch
    torch.cuda.empty_cache()
    
    return embeddings

# Load model
device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
model = ClayMAEModule.load_from_checkpoint(
    "clay-v1.5.ckpt",
    model_size="large",
    metadata_path="configs/metadata.yaml",
    dolls=[16, 32, 64, 128, 256, 768, 1024],
    doll_weights=[1, 1, 1, 1, 1, 1, 1],
    mask_ratio=0.0,
    shuffle=False,
    map_location=device
)
model.eval()
model = model.to(device)

print(f"Model loaded on {device}")

# LINZ metadata
from box import Box
import yaml
metadata = Box(yaml.safe_load(open("configs/metadata.yaml")))
platform = "linz-nir"
band_names = ['red', 'green', 'blue', 'nir']
mean = [metadata[platform].bands.mean[band] for band in band_names]
std = [metadata[platform].bands.std[band] for band in band_names]
waves = [metadata[platform].bands.wavelength[band] for band in band_names]
gsd = metadata[platform].gsd

# Setup paths
tile_base_name = Path(TILE_NAME).stem  # Remove .tiff extension
output_dir = Path("data") / tile_base_name
output_dir.mkdir(parents=True, exist_ok=True)

tif_path = Path("data") / TILE_NAME
tile_size = 256

with rasterio.open(tif_path) as src:
    height, width = src.height, src.width
    print(f"Image size: {width}x{height}")
    
    # Calculate number of tiles
    n_tiles_x = width // tile_size
    n_tiles_y = height // tile_size
    print(f"Processing {n_tiles_x}x{n_tiles_y} = {n_tiles_x * n_tiles_y} tiles")
    
    # Prepare output arrays
    embedding_dim = None
    patches_per_tile = None  # Will be determined from first tile
    embeddings_map = None
    print(f"Embedding mode: {EMBEDDING_MODE}")
    
    # Process each tile
    tile_count = 0
    for ty in range(n_tiles_y):
        for tx in range(n_tiles_x):
            tile_count += 1
            if tile_count % 10 == 0:
                print(f"Processing tile {tile_count}/{n_tiles_x * n_tiles_y}")
            
            # Read tile (4 bands: RGB + NIR)
            window = Window(tx * tile_size, ty * tile_size, tile_size, tile_size)
            tile_data = src.read([1, 2, 3, 4], window=window).astype(np.float32)
            
            # Normalize
            tile_tensor = torch.from_numpy(tile_data)
            for i, (m, s) in enumerate(zip(mean, std)):
                tile_tensor[i] = (tile_tensor[i] - m) / s
            
            # Get center lat/lon for tile
            center_x = (tx + 0.5) * tile_size
            center_y = (ty + 0.5) * tile_size
            lon, lat = src.xy(center_y, center_x)
            
            # Process tile
            embeddings = process_tile(model, tile_tensor, lat, lon, gsd, waves, platform, device, EMBEDDING_MODE)
            
            # Initialize embeddings_map on first tile
            if embeddings_map is None:
                embedding_dim = embeddings.shape[2]
                if EMBEDDING_MODE == "cls":
                    patches_per_tile = 1
                else:
                    n_patches = embeddings.shape[1]
                    patches_per_tile = int(n_patches ** 0.5)
                embeddings_map = np.zeros((n_tiles_y * patches_per_tile, n_tiles_x * patches_per_tile, embedding_dim), dtype=np.float32)
                print(f"Embedding dimension: {embedding_dim}")
                print(f"Patches per tile: {patches_per_tile}x{patches_per_tile}")
                print(f"Output resolution: {n_tiles_y * patches_per_tile} x {n_tiles_x * patches_per_tile} patches")
            
            # Reshape and place in output
            if EMBEDDING_MODE == "cls":
                embeddings_map[ty, tx] = embeddings[0, 0]
            else:
                patches_2d = embeddings[0].reshape(patches_per_tile, patches_per_tile, embedding_dim)
                embeddings_map[ty*patches_per_tile:(ty+1)*patches_per_tile, 
                              tx*patches_per_tile:(tx+1)*patches_per_tile] = patches_2d
            
            gc.collect()
    
    # Save embeddings as GeoTIFF - prepare profile before closing src
    output_profile = src.profile.copy()
    pixel_scale = tile_size // patches_per_tile if EMBEDDING_MODE == "patches" else tile_size
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
