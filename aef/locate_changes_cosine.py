"""Identify changes between two co-registered AlphaEarth embedding GeoTIFFs."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

DEFAULT_EARLIER = Path(r"C:\Data\AEF\wanaka\2019\xkmgcxnihpzce8az1-0000008192-0000000000.tiff")
DEFAULT_LATER = Path(r"C:\Data\AEF\wanaka\2024\xd8jjxuf7h0qy40py-0000008192-0000000000.tiff")
DEFAULT_OUTPUT_DIRECTORY = Path(r"C:\Data\AEF\wanaka\change_detection")
HISTOGRAM_BINS = 20_000
SUMMARY_PERCENTILES = np.array([50, 75, 90, 95, 99])


class CosineChangeDetector:
    """Compare two co-registered embedding rasters using cosine distance.

    The detector reads both rasters in windows, writes a continuous cosine
    distance raster, estimates a global threshold from the requested
    percentile, and writes a binary candidate-change mask. Input rasters must
    have identical bands, dimensions, CRS, and affine transform.

    Higher scores indicate a larger change in embedding direction. They are
    candidate changes rather than classified real-world change types.
    """

    def __init__(
        self,
        earlier_path: str | Path,
        later_path: str | Path,
        output_directory: str | Path,
        *,
        percentile: float = 95.0,
        block_size: int = 512,
    ) -> None:
        if not 0 < percentile < 100:
            raise ValueError("Percentile must be greater than 0 and less than 100.")
        if block_size <= 0:
            raise ValueError("Block size must be positive.")

        self.earlier_path = Path(earlier_path)
        self.later_path = Path(later_path)
        self.output_directory = Path(output_directory)
        self.percentile = percentile
        self.block_size = block_size

    @staticmethod
    def change_score(
        earlier: np.ndarray, later: np.ndarray, nodata: float | None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return cosine distance and validity for [bands, rows, columns] arrays."""
        valid = np.ones(earlier.shape[1:], dtype=bool)
        if nodata is not None:
            valid &= np.all(earlier != nodata, axis=0)
            valid &= np.all(later != nodata, axis=0)

        earlier = earlier.astype(np.float32, copy=False)
        later = later.astype(np.float32, copy=False)
        dot_product = np.einsum("ijk,ijk->jk", earlier, later, optimize=True)
        earlier_norm = np.linalg.norm(earlier, axis=0)
        later_norm = np.linalg.norm(later, axis=0)
        valid &= (earlier_norm > 0) & (later_norm > 0)

        score = np.full(earlier.shape[1:], np.nan, dtype=np.float32)
        score[valid] = 1.0 - dot_product[valid] / (
            earlier_norm[valid] * later_norm[valid]
        )
        return score, valid

    def windows(self, dataset: rasterio.DatasetReader):
        """Yield fixed-size windows covering a dataset."""
        for row_offset in range(0, dataset.height, self.block_size):
            for column_offset in range(0, dataset.width, self.block_size):
                yield Window(
                    column_offset,
                    row_offset,
                    min(self.block_size, dataset.width - column_offset),
                    min(self.block_size, dataset.height - row_offset),
                )

    @staticmethod
    def validate_inputs(
        earlier: rasterio.DatasetReader, later: rasterio.DatasetReader
    ) -> None:
        """Raise when embeddings cannot be compared pixel by pixel."""
        matching_grid = (
            earlier.count == later.count
            and earlier.width == later.width
            and earlier.height == later.height
            and earlier.crs == later.crs
            and earlier.transform == later.transform
        )
        if not matching_grid:
            raise ValueError(
                "Embedding rasters must have matching bands, grid, CRS, and transform."
            )

    @staticmethod
    def percentile_from_histogram(histogram: np.ndarray, percentile: float) -> float:
        """Estimate a percentile from cosine-distance bins spanning [0, 2]."""
        target_count = histogram.sum() * percentile / 100
        percentile_bin = np.searchsorted(np.cumsum(histogram), target_count)
        return float(percentile_bin * 2 / histogram.size)

    def run(self) -> tuple[Path, Path, float, dict[int, float]]:
        """Write score and mask GeoTIFFs, then return paths and score statistics."""
        self.output_directory.mkdir(parents=True, exist_ok=True)
        scores_path = self.output_directory / "cosine_change_score.tif"
        mask_path = self.output_directory / "change_mask.tif"
        histogram = np.zeros(HISTOGRAM_BINS, dtype=np.int64)

        with rasterio.open(self.earlier_path) as earlier, rasterio.open(
            self.later_path
        ) as later:
            self.validate_inputs(earlier, later)
            nodata = earlier.nodata if earlier.nodata is not None else later.nodata
            profile = earlier.profile.copy()
            profile.update(count=1, dtype="float32", nodata=np.nan, compress="deflate")

            with rasterio.open(scores_path, "w", **profile) as score_dataset:
                for window in self.windows(earlier):
                    score, valid = self.change_score(
                        earlier.read(window=window), later.read(window=window), nodata
                    )
                    score_dataset.write(score, 1, window=window)
                    histogram += np.histogram(
                        score[valid], bins=HISTOGRAM_BINS, range=(0, 2)
                    )[0]

            if histogram.sum() == 0:
                raise ValueError(
                    "The embedding rasters contain no mutually valid pixels."
                )

            threshold = self.percentile_from_histogram(histogram, self.percentile)
            score_percentiles = {
                int(summary_percentile): self.percentile_from_histogram(
                    histogram, summary_percentile
                )
                for summary_percentile in SUMMARY_PERCENTILES
            }
            mask_profile = profile.copy()
            mask_profile.update(dtype="uint8", nodata=0)

            with rasterio.open(scores_path) as score_dataset, rasterio.open(
                mask_path, "w", **mask_profile
            ) as mask_dataset:
                for window in self.windows(score_dataset):
                    score = score_dataset.read(1, window=window)
                    mask = np.where(
                        np.isfinite(score) & (score > threshold), 1, 0
                    ).astype(np.uint8)
                    mask_dataset.write(mask, 1, window=window)

        return scores_path, mask_path, threshold, score_percentiles


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--earlier", type=Path, default=DEFAULT_EARLIER)
    parser.add_argument("--later", type=Path, default=DEFAULT_LATER)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--percentile", type=float, default=95.0)
    parser.add_argument("--block-size", type=int, default=512)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    detector = CosineChangeDetector(
        earlier_path=arguments.earlier,
        later_path=arguments.later,
        output_directory=arguments.output_directory,
        percentile=arguments.percentile,
        block_size=arguments.block_size,
    )
    score_path, change_mask_path, change_threshold, score_percentiles = detector.run()
    print(f"Change-score raster: {score_path}")
    print(f"Change mask: {change_mask_path}")
    print(f"Cosine-distance threshold: {change_threshold:.5f}")
    print("Change-score percentiles:")
    for percentile, score in score_percentiles.items():
        print(f"  {percentile:>2}th: {score:.5f}")

