"""Visualize spatial feature maps from a Clay embeddings GeoTIFF."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio

def parse_dimensions(value: str) -> list[int]:
    """Parse a comma-separated list of zero-based embedding dimensions."""
    try:
        dimensions = [int(item.strip()) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("Dimensions must be comma-separated integers.") from error

    if not dimensions or any(dimension < 0 for dimension in dimensions):
        raise argparse.ArgumentTypeError("Dimensions must be non-negative integers.")
    return dimensions

def visualize_embeddings(
    embedding_path: Path,
    dimensions: list[int],
    output_directory: Path | None = None,
    rows: int = 5,
    columns: int = 4,
) -> list[Path]:
    """Plot selected embedding dimensions in paginated spatial feature-map grids."""
    with rasterio.open(embedding_path) as dataset:
        if max(dimensions) >= dataset.count:
            raise ValueError(
                f"Requested dimension {max(dimensions)}, but the file has {dataset.count} bands."
            )
        output_directory = output_directory or embedding_path.parent
        output_directory.mkdir(parents=True, exist_ok=True)
        dimensions_per_page = rows * columns
        output_paths = []

        for page_number, start in enumerate(range(0, len(dimensions), dimensions_per_page), start=1):
            page_dimensions = dimensions[start : start + dimensions_per_page]
            embeddings = dataset.read([dimension + 1 for dimension in page_dimensions])
            figure, axes = plt.subplots(
                rows, columns, figsize=(4 * columns, 3.5 * rows), squeeze=False
            )

            for axis, dimension, embedding in zip(axes.flat, page_dimensions, embeddings):
                axis.imshow(embedding, cmap="bwr")
                axis.set_title(f"Embedding dimension {dimension}")
                axis.set_axis_off()

            for axis in axes.flat[len(page_dimensions) :]:
                axis.set_visible(False)

            figure.tight_layout()
            output_path = output_directory / f"{embedding_path.stem}_dimensions_{page_number:02d}.png"
            figure.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close(figure)
            output_paths.append(output_path)

    return output_paths

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize selected Clay embedding dimensions from a GeoTIFF."
    )
    parser.add_argument(
        "embeddings",
        type=Path,
        help="Path to a patch-embeddings GeoTIFF, such as nz_embeddings_tiled.tif.",
    )
    dimension_group = parser.add_mutually_exclusive_group()
    dimension_group.add_argument(
        "--dimensions",
        type=parse_dimensions,
        help="Zero-based dimensions to plot, separated by commas.",
    )
    dimension_group.add_argument(
        "--step",
        type=int,
        default=10,
        help="Plot every Nth embedding dimension (default: 10).",
    )
    parser.add_argument("--output-dir", type=Path, help="Directory for the output PNGs.")
    args = parser.parse_args()

    if args.step < 1:
        parser.error("--step must be at least 1.")
    if not args.embeddings.is_file():
        parser.error(f"Embeddings file not found: {args.embeddings}")

    with rasterio.open(args.embeddings) as dataset:
        dimensions = args.dimensions or list(range(0, dataset.count, args.step))

    output_paths = visualize_embeddings(args.embeddings, dimensions, args.output_dir)
    for output_path in output_paths:
        print(f"Saved visualization to {output_path}")

if __name__ == "__main__":
    main()