import torch
import numpy as np
import rasterio
from rasterio.windows import Window
from claymodel.module import ClayMAEModule
from pathlib import Path
from box import Box
import yaml

# Configuration
#TILE_NAME = "BA31_10000_0405.tiff"
TILE_NAME = "BA31_10000_0505.tiff"
EMBEDDING_MODE = "cls" ##"patches"  # or "cls"
BATCH_SIZE = 16  # Process 16 tiles at once
CHECKPOINT_EVERY = 512  # Save progress every N tiles

def process_batch(model, batch_pixels, batch_latlons, gsd, waves, platform, device, mode="patches"):
    """Process a batch of tiles through the model."""
    batch_size = len(batch_pixels)
    week = 1 * 2 * np.pi / 52
    hour = 12 * 2 * np.pi / 24
    
    # Build batched datacube
    time_batch = torch.tensor([[np.sin(week), np.cos(week), np.sin(hour), np.cos(hour)]] * batch_size, 
                              dtype=torch.float32, device=device)
    latlon_batch = torch.stack([
        torch.tensor([np.sin(lat * np.pi / 180), np.cos(lat * np.pi / 180), 
                     np.sin(lon * np.pi / 180), np.cos(lon * np.pi / 180)], 
                    dtype=torch.float32, device=device)
        for lat, lon in batch_latlons
    ])
    pixels_batch = torch.stack(batch_pixels).to(device)
    
    datacube = {
        "platform": platform,
        "time": time_batch,
        "latlon": latlon_batch,
        "pixels": pixels_batch,
        "gsd": torch.tensor(gsd, dtype=torch.float32, device=device),
        "waves": torch.tensor(waves, dtype=torch.float32, device=device),
    }
    
    with torch.no_grad():
        unmsk_patch, _, _, _ = model.model.encoder(datacube)
        if mode == "cls":
            embeddings = unmsk_patch[:, 0:1, :].cpu().numpy()
        else:
            embeddings = unmsk_patch[:, 1:, :].cpu().numpy()
    
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

# Load metadata
metadata = Box(yaml.safe_load(open("configs/metadata.yaml")))
platform = "linz-nir"
band_names = ['red', 'green', 'blue', 'nir']
mean = [metadata[platform].bands.mean[band] for band in band_names]
std = [metadata[platform].bands.std[band] for band in band_names]
waves = [metadata[platform].bands.wavelength[band] for band in band_names]
gsd = metadata[platform].gsd

# Setup paths
tile_base_name = Path(TILE_NAME).stem
output_dir = Path("data") / tile_base_name
output_dir.mkdir(parents=True, exist_ok=True)

tif_path = Path("data") / TILE_NAME
tile_size = 256

with rasterio.open(tif_path) as src:
    height, width = src.height, src.width
    n_tiles_x = width // tile_size
    n_tiles_y = height // tile_size
    total_tiles = n_tiles_x * n_tiles_y
    
    print(f"Image size: {width}x{height}")
    print(f"Processing {n_tiles_x}x{n_tiles_y} = {total_tiles} tiles in batches of {BATCH_SIZE}")
    print(f"Embedding mode: {EMBEDDING_MODE}")
    
    # Collect all tile data
    batch_pixels = []
    batch_latlons = []
    batch_positions = []
    embeddings_map = None
    embedding_dim = None
    patches_per_tile = None
    
    for ty in range(n_tiles_y):
        for tx in range(n_tiles_x):
            # Read tile
            window = Window(tx * tile_size, ty * tile_size, tile_size, tile_size)
            tile_data = src.read([1, 2, 3, 4], window=window).astype(np.float32)
            
            # Normalize
            tile_tensor = torch.from_numpy(tile_data)
            for i, (m, s) in enumerate(zip(mean, std)):
                tile_tensor[i] = (tile_tensor[i] - m) / s
            
            # Get lat/lon
            center_x = (tx + 0.5) * tile_size
            center_y = (ty + 0.5) * tile_size
            lon, lat = src.xy(center_y, center_x)
            
            batch_pixels.append(tile_tensor)
            batch_latlons.append((lat, lon))
            batch_positions.append((ty, tx))
            
            # Process batch when full
            if len(batch_pixels) == BATCH_SIZE or (ty == n_tiles_y - 1 and tx == n_tiles_x - 1):
                try:
                    embeddings = process_batch(model, batch_pixels, batch_latlons, gsd, waves, platform, device, EMBEDDING_MODE)
                except Exception as e:
                    print(f"Error at tile {ty * n_tiles_x + tx + 1}: {e}")
                    raise
                
                # Initialize output on first batch
                if embeddings_map is None:
                    embedding_dim = embeddings.shape[2]
                    if EMBEDDING_MODE == "cls":
                        patches_per_tile = 1
                    else:
                        patches_per_tile = int(embeddings.shape[1] ** 0.5)
                    embeddings_map = np.zeros((n_tiles_y * patches_per_tile, n_tiles_x * patches_per_tile, embedding_dim), dtype=np.float32)
                    print(f"Embedding dimension: {embedding_dim}")
                    print(f"Patches per tile: {patches_per_tile}x{patches_per_tile}")
                
                # Place embeddings
                for i, (ty_pos, tx_pos) in enumerate(batch_positions):
                    if EMBEDDING_MODE == "cls":
                        embeddings_map[ty_pos, tx_pos] = embeddings[i, 0]
                    else:
                        patches_2d = embeddings[i].reshape(patches_per_tile, patches_per_tile, embedding_dim)
                        embeddings_map[ty_pos*patches_per_tile:(ty_pos+1)*patches_per_tile,
                                      tx_pos*patches_per_tile:(tx_pos+1)*patches_per_tile] = patches_2d
                
                processed = (ty * n_tiles_x + tx + 1)
                print(f"Processed {processed}/{total_tiles} tiles")
                
                # Checkpoint progress
                if processed % CHECKPOINT_EVERY == 0:
                    checkpoint_path = output_dir / f"checkpoint_{processed}.npy"
                    np.save(checkpoint_path, embeddings_map)
                    print(f"Checkpoint saved: {checkpoint_path}")
                
                # Clear batch
                batch_pixels = []
                batch_latlons = []
                batch_positions = []
    
    # Prepare output profile
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
