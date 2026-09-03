import torch
import numpy as np
import rasterio
from rasterio.windows import Window
from claymodel.module import ClayMAEModule
import gc

def process_tile(model, pixels, lat, lon, gsd, waves, platform, device):
    """Process a single 256x256 tile through the model."""
    week = 1 * 2 * np.pi / 52
    hour = 12 * 2 * np.pi / 24
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
    
    with torch.no_grad():
        unmsk_patch, _, _, _ = model.model.encoder(datacube)
        embedding = unmsk_patch[:, 0, :].cpu().numpy()
    
    del datacube, unmsk_patch
    torch.cuda.empty_cache()
    
    return embedding

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

# Processing parameters
tif_path = "data/AY30_1000_4448.tiff"
tile_size = 256
stride = 64  # Overlapping stride for ~5m resolution (64 * 0.075m = 4.8m)

with rasterio.open(tif_path) as src:
    height, width = src.height, src.width
    print(f"Image size: {width}x{height}")
    
    # Calculate output dimensions
    n_tiles_x = (width - tile_size) // stride + 1
    n_tiles_y = (height - tile_size) // stride + 1
    print(f"Processing {n_tiles_x}x{n_tiles_y} = {n_tiles_x * n_tiles_y} overlapping tiles")
    print(f"Output resolution: {stride * 0.075:.1f}m")
    
    embedding_dim = None
    embeddings_map = None
    
    tile_count = 0
    for ty in range(n_tiles_y):
        for tx in range(n_tiles_x):
            tile_count += 1
            if tile_count % 50 == 0:
                print(f"Processing tile {tile_count}/{n_tiles_x * n_tiles_y}")
            
            # Read overlapping tile
            start_x = tx * stride
            start_y = ty * stride
            window = Window(start_x, start_y, tile_size, tile_size)
            tile_data = src.read([1, 2, 3], window=window).astype(np.float32)
            
            # Normalize
            tile_tensor = torch.from_numpy(tile_data)
            for i, (m, s) in enumerate(zip(mean, std)):
                tile_tensor[i] = (tile_tensor[i] - m) / s
            
            # Get center lat/lon
            center_x = start_x + tile_size / 2
            center_y = start_y + tile_size / 2
            lon, lat = src.xy(center_y, center_x)
            
            # Process tile
            embedding = process_tile(model, tile_tensor, lat, lon, gsd, waves, platform, device)
            
            # Initialize on first tile
            if embeddings_map is None:
                embedding_dim = embedding.shape[1]
                embeddings_map = np.zeros((n_tiles_y, n_tiles_x, embedding_dim), dtype=np.float32)
                print(f"Embedding dimension: {embedding_dim}")
            
            embeddings_map[ty, tx] = embedding[0]
            gc.collect()
    
    # Save with updated transform
    output_profile = src.profile.copy()
    output_profile.update({
        'count': embedding_dim,
        'dtype': 'float32',
        'width': n_tiles_x,
        'height': n_tiles_y,
        'transform': src.transform * src.transform.scale(stride, stride)
    })

print(f"All tiles processed. Embeddings shape: {embeddings_map.shape}")

with rasterio.open("data/nz_embeddings_highres.tif", "w", **output_profile) as dst:
    for i in range(embedding_dim):
        dst.write(embeddings_map[:, :, i], i + 1)

print("High-res embeddings saved to data/nz_embeddings_highres.tif")
