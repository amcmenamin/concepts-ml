"""Trial k-nearest-neighbour novelty scoring for AlphaEarth embedding GeoTIFFs.

A 2024 embedding is novel when its mean distance to its k closest sampled 2019
embeddings is high. Scores are computed on a coarse grid because an exact kNN
search across both full 8192 x 8192 rasters is prohibitively expensive.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from sklearn.neighbors import NearestNeighbors

DEFAULT_EARLIER = Path(r"C:\Data\AEF\wanaka\2019\xkmgcxnihpzce8az1-0000008192-0000000000.tiff")
DEFAULT_LATER = Path(r"C:\Data\AEF\wanaka\2024\xd8jjxuf7h0qy40py-0000008192-0000000000.tiff")
DEFAULT_OUTPUT_DIRECTORY = Path(r"C:\Data\AEF\wanaka\change_detection")


def validate_inputs(earlier: rasterio.DatasetReader, later: rasterio.DatasetReader) -> None:
    """Raise when embeddings cannot be compared on the same spatial grid."""
    matching_grid = (
        earlier.count == later.count
        and earlier.width == later.width
        and earlier.height == later.height
        and earlier.crs == later.crs
        and earlier.transform == later.transform
    )
    if not matching_grid:
        raise ValueError("Embedding rasters must have matching bands, grid, CRS, and transform.")


def embedding_vectors(dataset: rasterio.DatasetReader, stride: int) -> tuple[np.ndarray, np.ndarray]:
    """Read a nearest-neighbour-resampled embedding grid as vectors and validity mask."""
    height = (dataset.height + stride - 1) // stride
    width = (dataset.width + stride - 1) // stride
    embeddings = dataset.read(
        out_shape=(dataset.count, height, width), resampling=Resampling.nearest
    )
    valid = np.ones((height, width), dtype=bool)
    if dataset.nodata is not None:
        valid &= np.all(embeddings != dataset.nodata, axis=0)

    vectors = np.moveaxis(embeddings, 0, -1).reshape(-1, dataset.count).astype(np.float32)
    valid = valid.ravel()
    valid &= np.linalg.norm(vectors, axis=1) > 0
    return vectors, valid


def novelty_scores(
    reference_vectors: np.ndarray, query_vectors: np.ndarray, neighbours: int
) -> np.ndarray:
    """Return mean Euclidean distance to the k nearest reference embeddings."""
    model = NearestNeighbors(n_neighbors=neighbours, algorithm="auto", n_jobs=-1)
    model.fit(reference_vectors)
    distances, _ = model.kneighbors(query_vectors)
    return distances.mean(axis=1)


def detect_novelty(
    earlier_path: Path,
    later_path: Path,
    output_path: Path,
    stride: int,
    reference_samples: int,
    neighbours: int,
    seed: int,
) -> Path:
    """Write a coarse GeoTIFF of 2024 novelty relative to 2019 embedding samples."""
    if stride <= 0 or reference_samples <= 0 or neighbours <= 0:
        raise ValueError("Stride, reference samples, and neighbours must be positive.")

    with rasterio.open(earlier_path) as earlier, rasterio.open(later_path) as later:
        validate_inputs(earlier, later)
        earlier_vectors, earlier_valid = embedding_vectors(earlier, stride)
        later_vectors, later_valid = embedding_vectors(later, stride)

        available_reference = earlier_vectors[earlier_valid]
        if available_reference.size == 0 or later_valid.sum() == 0:
            raise ValueError("The embedding rasters contain no mutually usable vectors.")

        sample_count = min(reference_samples, len(available_reference))
        if neighbours > sample_count:
            raise ValueError("Neighbours cannot exceed the number of reference samples.")
        random_generator = np.random.default_rng(seed)
        sample_indices = random_generator.choice(len(available_reference), sample_count, replace=False)
        reference_vectors = available_reference[sample_indices]

        output_height = (earlier.height + stride - 1) // stride
        output_width = (earlier.width + stride - 1) // stride
        scores = np.full(output_height * output_width, np.nan, dtype=np.float32)
        scores[later_valid] = novelty_scores(
            reference_vectors, later_vectors[later_valid], neighbours
        )
        scores = scores.reshape(output_height, output_width)

        profile = earlier.profile.copy()
        profile.update(
            count=1,
            dtype="float32",
            height=output_height,
            width=output_width,
            transform=earlier.transform * Affine.scale(stride, stride),
            nodata=np.nan,
            compress="deflate",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **profile) as output_dataset:
            output_dataset.write(scores, 1)

    return output_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--earlier", type=Path, default=DEFAULT_EARLIER)
    parser.add_argument("--later", type=Path, default=DEFAULT_LATER)
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_DIRECTORY / "knn_novelty_score.tif"
    )
    parser.add_argument("--stride", type=int, default=16)
    parser.add_argument("--reference-samples", type=int, default=10_000)
    parser.add_argument("--neighbours", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    novelty_path = detect_novelty(
        arguments.earlier,
        arguments.later,
        arguments.output,
        arguments.stride,
        arguments.reference_samples,
        arguments.neighbours,
        arguments.seed,
    )
    print(f"kNN novelty-score raster: {novelty_path}")
