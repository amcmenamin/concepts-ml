"""Run raster items export for multiple S3 folders."""

from __future__ import annotations

import time
from pathlib import Path

from export_raster_items import RasterItemsExporter

# Configure one or more S3 folders to export.
# Each entry is a dict with:
#   - source: S3 folder or bucket-relative prefix
#   - output_location: absolute local directory for output
#   - geoparquet (optional): custom output GeoParquet path
#   - exclude_filename (optional): filename to exclude (default: collection.json)
EXPORTS = [
    {
        "source": "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193",
        "output_location": r"C:\Data\clay\wellington\raster_items",
    },
    # Add more entries as needed:
    # {
    #     "source": "wellington/hutt-city_2025_0.075m/rgb/2193",
    #     "output_location": r"C:\Data\clay\wellington\raster_items_2",
    #     "geoparquet": r"C:\Data\clay\wellington\raster_items_2\custom_name.parquet",
    # },
]


def main() -> None:
    start_time = time.perf_counter()
    total_features = 0

    for index, config in enumerate(EXPORTS, start=1):
        print(f"\n[{index}/{len(EXPORTS)}] Processing {config['source']}")
        try:
            exporter = RasterItemsExporter(
                source=config["source"],
                output_location=config["output_location"],
                exclude_filename=config.get("exclude_filename", "collection.json"),
            )
            geoparquet_path, feature_count = exporter.build_geoparquet(
                config.get("geoparquet")
            )
            total_features += feature_count
            print(f"  ✓ Wrote {feature_count} feature(s) to {geoparquet_path}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    elapsed_seconds = time.perf_counter() - start_time
    print(f"\n{'=' * 60}")
    print(f"Total features exported: {total_features}")
    print(f"Completed in {elapsed_seconds:.3f} seconds")


if __name__ == "__main__":
    main()
