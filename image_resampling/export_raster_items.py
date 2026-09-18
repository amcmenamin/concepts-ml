"""Export JSON features from an S3 folder and combine into a GeoParquet dataset.

Recursively searches for JSON files (excluding collection.json) beneath an S3
prefix, parses each as GeoJSON-like features, and combines them into a single
GeoParquet file with all properties preserved.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path, PurePosixPath

import geopandas as gpd
import obstore as obs
import pandas as pd
from shapely.geometry import shape

from resample_aws_imagery import (
    AWS_REGION,
    SOURCE_BUCKET,
    build_s3_uri,
    get_public_store,
    is_absolute_local_path,
    parse_s3_path,
)


class RasterItemsExporter:
    """Find and export JSON feature files from a public S3 prefix.

    Reads JSON files (excluding collection.json) that contain GeoJSON features,
    combines them into a single GeoDataFrame, and saves as GeoParquet.
    """

    def __init__(
        self,
        source: str,
        output_location: str,
        *,
        exclude_filename: str = "collection.json",
        source_bucket: str = SOURCE_BUCKET,
        aws_region: str = AWS_REGION,
    ) -> None:
        self.source_bucket, self.prefix = parse_s3_path(
            source,
            source_bucket=source_bucket,
            aws_region=aws_region,
        )
        self.prefix = self.prefix.rstrip("/")
        if not is_absolute_local_path(output_location):
            raise ValueError(
                "A local absolute output directory is required to build GeoParquet"
            )
        self.output_location = output_location
        self.output_root = Path(output_location).expanduser()
        self.exclude_filename = exclude_filename
        self.aws_region = aws_region
        self.source_store = get_public_store(self.source_bucket, aws_region)

    def find_json_files(self) -> list[str]:
        """Return matching .json object keys recursively beneath the source prefix."""
        listing_prefix = f"{self.prefix}/" if self.prefix else ""
        return sorted(
            item["path"]
            for chunk in obs.list(self.source_store, prefix=listing_prefix)
            for item in chunk
            if (
                PurePosixPath(item["path"]).suffix == ".json"
                and PurePosixPath(item["path"]).name != self.exclude_filename
            )
        )

    def download_json_file(self, s3_key: str) -> dict:
        """Download and parse a JSON file from S3."""
        try:
            data = bytes(obs.get(self.source_store, s3_key).bytes())
            return json.loads(data.decode())
        except Exception as e:
            raise ValueError(f"Failed to download or parse {s3_key}: {e}") from e

    def get_collection_name(self) -> str:
        """Extract collection name (element before /rgb or /rgbnir) from prefix."""
        parts = PurePosixPath(self.prefix).parts
        for i, part in enumerate(parts):
            if part in ("rgb", "rgbnir"):
                # Return the part before rgb/rgbnir
                if i > 0:
                    return parts[i - 1]
        # Fallback: use the last part if no rgb/rgbnir found
        return parts[-1] if parts else "features"

    @property
    def hierarchy_root(self) -> Path:
        """Return the local directory corresponding to the searched S3 prefix."""
        return self.output_root.joinpath(*PurePosixPath(self.prefix).parts)

    def build_geoparquet(
        self, output_path: str | Path | None = None
    ) -> tuple[Path, int]:
        """Read JSON files from S3 and write a combined GeoParquet dataset."""
        json_files = self.find_json_files()
        if not json_files:
            raise FileNotFoundError(
                f"No .json files found beneath {self.prefix} "
                f"(excluding {self.exclude_filename})"
            )

        frames: list[gpd.GeoDataFrame] = []
        target_crs = None
        
        for index, s3_key in enumerate(json_files, start=1):
            print(f"[{index}/{len(json_files)}] Processing {s3_key}")
            
            try:
                feature_data = self.download_json_file(s3_key)
                
                # Extract geometry and properties
                if "geometry" not in feature_data:
                    raise ValueError(f"No geometry found in {s3_key}")
                
                geometry = shape(feature_data["geometry"])
                
                # Collect all properties
                row_data = {}
                if "properties" in feature_data:
                    row_data.update(feature_data["properties"])
                if "id" in feature_data:
                    row_data["feature_id"] = feature_data["id"]
                
                # Add S3 path for reference
                row_data["s3_path"] = build_s3_uri(self.source_bucket, s3_key)
                
                # Create GeoDataFrame from this feature
                gdf = gpd.GeoDataFrame(
                    [row_data],
                    geometry=[geometry],
                    crs="EPSG:4326",  # Assume WGS84 for JSON features
                )
                
                # Handle CRS consistency
                if target_crs is None:
                    target_crs = gdf.crs
                elif gdf.crs != target_crs:
                    gdf = gdf.to_crs(target_crs)
                
                frames.append(gdf)
                
            except Exception as e:
                print(f"  Warning: Skipped {s3_key}: {e}")
                continue

        if not frames:
            raise ValueError("No valid features were extracted from JSON files")

        combined = gpd.GeoDataFrame(
            pd.concat(frames, ignore_index=True),
            geometry="geometry",
            crs=target_crs,
        )
        
        geoparquet_path = (
            Path(output_path).expanduser()
            if output_path is not None
            else self.output_root / f"{self.get_collection_name()}.parquet"
        )
        geoparquet_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(geoparquet_path, index=False)
        return geoparquet_path, len(combined)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        help="S3 folder or bucket-relative prefix to search recursively",
    )
    parser.add_argument(
        "--output",
        required=True,
        dest="output_location",
        help="Absolute local output directory",
    )
    parser.add_argument(
        "--geoparquet",
        type=Path,
        help="Output GeoParquet path (default: OUTPUT/features.parquet)",
    )
    parser.add_argument(
        "--exclude",
        default="collection.json",
        help="Filename to exclude from processing (default: collection.json)",
    )
    parser.add_argument(
        "--source-bucket",
        default=SOURCE_BUCKET,
        help=f"Bucket for relative source prefixes (default: {SOURCE_BUCKET})",
    )
    parser.add_argument(
        "--aws-region",
        default=AWS_REGION,
        help=f"AWS region for S3 access (default: {AWS_REGION})",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    start_time = time.perf_counter()
    
    exporter = RasterItemsExporter(
        source=arguments.source,
        output_location=arguments.output_location,
        exclude_filename=arguments.exclude,
        source_bucket=arguments.source_bucket,
        aws_region=arguments.aws_region,
    )
    
    geoparquet_path, feature_count = exporter.build_geoparquet(arguments.geoparquet)
    elapsed_seconds = time.perf_counter() - start_time
    
    print(f"Wrote {feature_count} feature(s) to {geoparquet_path}")
    print(f"Completed in {elapsed_seconds:.3f} seconds")


if __name__ == "__main__":
    main()
