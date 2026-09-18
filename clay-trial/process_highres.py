"""High-resolution Clay embedding processor for large raster images.

Processes large raster images by extracting overlapping tiles and generating
Clay embeddings at higher spatial resolution than standard tile-based processing.
"""

from __future__ import annotations

import gc
from pathlib import Path

import numpy as np
import rasterio
import torch
import yaml
from box import Box
from claymodel.module import ClayMAEModule
from rasterio.windows import Window


class HighResClayProcessor:
    """Process large rasters with overlapping tiles for high-resolution embeddings."""

    def __init__(
        self,
        checkpoint_path: str | Path,
        metadata_path: str | Path,
        *,
        tile_size: int = 256,
        stride: int = 64,
        model_size: str = "large",
        mask_ratio: float = 0.0,
    ) -> None:
        """Initialize the high-resolution processor.

        Args:
            checkpoint_path: Path to Clay model checkpoint (.ckpt file)
            metadata_path: Path to metadata YAML configuration
            tile_size: Size of tiles to extract (default: 256)
            stride: Stride between tiles for overlap (default: 64)
            model_size: Clay model size (default: "large")
            mask_ratio: Masking ratio for model (default: 0.0)
        """
        self.checkpoint_path = Path(checkpoint_path)
        self.metadata_path = Path(metadata_path)
        self.tile_size = tile_size
        self.stride = stride
        self.model_size = model_size
        self.mask_ratio = mask_ratio

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.metadata = None
        self.platform = "linz-nir"
        self.band_names = ["red", "green", "blue", "nir"]

    def load_model(self) -> None:
        """Load Clay model and metadata."""
        self.model = ClayMAEModule.load_from_checkpoint(
            str(self.checkpoint_path),
            model_size=self.model_size,
            metadata_path=str(self.metadata_path),
            dolls=[16, 32, 64, 128, 256, 768, 1024],
            doll_weights=[1, 1, 1, 1, 1, 1, 1],
            mask_ratio=self.mask_ratio,
            shuffle=False,
            map_location=self.device,
        )
        self.model.eval()
        self.model = self.model.to(self.device)

        self.metadata = Box(yaml.safe_load(open(self.metadata_path)))
        print(f"Model loaded on {self.device}")

    def _get_normalization_params(self) -> tuple[list[float], list[float], list[float], float]:
        """Get normalization parameters from metadata."""
        mean = [self.metadata[self.platform].bands.mean[band] for band in self.band_names]
        std = [self.metadata[self.platform].bands.std[band] for band in self.band_names]
        waves = [self.metadata[self.platform].bands.wavelength[band] for band in self.band_names]
        gsd = self.metadata[self.platform].gsd
        return mean, std, waves, gsd

    def _process_tile(
        self,
        pixels: torch.Tensor,
        lat: float,
        lon: float,
        gsd: float,
        waves: list[float],
    ) -> np.ndarray:
        """Process a single tile through the model.

        Args:
            pixels: Normalized pixel tensor
            lat: Latitude of tile center
            lon: Longitude of tile center
            gsd: Ground sampling distance
            waves: Wavelengths for bands

        Returns:
            Embedding array for the tile
        """
        week = 1 * 2 * np.pi / 52
        hour = 12 * 2 * np.pi / 24
        lat_rad = lat * np.pi / 180
        lon_rad = lon * np.pi / 180

        datacube = {
            "platform": self.platform,
            "time": torch.tensor(
                [[np.sin(week), np.cos(week), np.sin(hour), np.cos(hour)]],
                dtype=torch.float32,
                device=self.device,
            ),
            "latlon": torch.tensor(
                [[np.sin(lat_rad), np.cos(lat_rad), np.sin(lon_rad), np.cos(lon_rad)]],
                dtype=torch.float32,
                device=self.device,
            ),
            "pixels": pixels.unsqueeze(0).to(self.device),
            "gsd": torch.tensor(gsd, dtype=torch.float32, device=self.device),
            "waves": torch.tensor(waves, dtype=torch.float32, device=self.device),
        }

        with torch.no_grad():
            unmsk_patch, _, _, _ = self.model.model.encoder(datacube)
            embedding = unmsk_patch[:, 0, :].cpu().numpy()

        del datacube, unmsk_patch
        torch.cuda.empty_cache()

        return embedding

    def process_image(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        """Process a raster image with overlapping tiles.

        Args:
            input_path: Path to input raster file
            output_path: Path for output embedding raster

        Returns:
            Path to output file
        """
        if self.model is None:
            self.load_model()

        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        mean, std, waves, gsd = self._get_normalization_params()

        with rasterio.open(input_path) as src:
            height, width = src.height, src.width
            print(f"Image size: {width}x{height}")

            n_tiles_x = (width - self.tile_size) // self.stride + 1
            n_tiles_y = (height - self.tile_size) // self.stride + 1
            print(f"Processing {n_tiles_x}x{n_tiles_y} = {n_tiles_x * n_tiles_y} overlapping tiles")
            print(f"Output resolution: {self.stride * 0.075:.1f}m")

            embedding_dim = None
            embeddings_map = None
            tile_count = 0

            for ty in range(n_tiles_y):
                for tx in range(n_tiles_x):
                    tile_count += 1
                    if tile_count % 50 == 0:
                        print(f"Processing tile {tile_count}/{n_tiles_x * n_tiles_y}")

                    start_x = tx * self.stride
                    start_y = ty * self.stride
                    window = Window(start_x, start_y, self.tile_size, self.tile_size)
                    tile_data = src.read([1, 2, 3], window=window).astype(np.float32)

                    tile_tensor = torch.from_numpy(tile_data)
                    for i, (m, s) in enumerate(zip(mean, std)):
                        tile_tensor[i] = (tile_tensor[i] - m) / s

                    center_x = start_x + self.tile_size / 2
                    center_y = start_y + self.tile_size / 2
                    lon, lat = src.xy(center_y, center_x)

                    embedding = self._process_tile(tile_tensor, lat, lon, gsd, waves)

                    if embeddings_map is None:
                        embedding_dim = embedding.shape[1]
                        embeddings_map = np.zeros((n_tiles_y, n_tiles_x, embedding_dim), dtype=np.float32)
                        print(f"Embedding dimension: {embedding_dim}")

                    embeddings_map[ty, tx] = embedding[0]
                    gc.collect()

            output_profile = src.profile.copy()
            output_profile.update({
                "count": embedding_dim,
                "dtype": "float32",
                "width": n_tiles_x,
                "height": n_tiles_y,
                "transform": src.transform * src.transform.scale(self.stride, self.stride),
            })

        print(f"All tiles processed. Embeddings shape: {embeddings_map.shape}")

        with rasterio.open(output_path, "w", **output_profile) as dst:
            for i in range(embedding_dim):
                dst.write(embeddings_map[:, :, i], i + 1)

        print(f"High-res embeddings saved to {output_path}")
        return output_path
