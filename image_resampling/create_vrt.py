"""Create a VRT (Virtual Raster) file referencing raster files in a folder.

Supports local paths (Windows/Linux) and S3 locations. The VRT file can reference
TIFF, GeoTIFF, JPEG2000, and other raster formats supported by GDAL.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path, PurePosixPath

import obstore as obs
from rasterio.vrt import WarpedVRT

from resample_aws_imagery import (
    AWS_REGION,
    SOURCE_BUCKET,
    build_s3_uri,
    get_public_store,
    is_absolute_local_path,
    parse_s3_path,
)

logger = logging.getLogger(__name__)

# Supported raster file extensions
RASTER_EXTENSIONS = {".tif", ".tiff", ".jp2", ".jpg2", ".png", ".img"}


class VrtBuilder:
    """Create VRT files from raster files in a local or S3 folder."""

    def __init__(
        self,
        source: str,
        output_path: str | Path,
        *,
        source_bucket: str = SOURCE_BUCKET,
        aws_region: str = AWS_REGION,
        no_data: str | int | float = 0,
    ) -> None:
        self.output_path = Path(output_path).expanduser()
        self.aws_region = aws_region
        self.no_data = no_data

        # Check if source is local or S3
        if is_absolute_local_path(source):
            self.is_local = True
            self.source_path = Path(source).expanduser()
        else:
            self.is_local = False
            self.source_bucket, self.prefix = parse_s3_path(
                source,
                source_bucket=source_bucket,
                aws_region=aws_region,
            )
            self.prefix = self.prefix.rstrip("/")
            self.source_store = get_public_store(self.source_bucket, aws_region)

    def find_rasters_local(self) -> list[str]:
        """Find all raster files in local directory recursively."""
        if not self.source_path.exists():
            raise FileNotFoundError(f"Local path does not exist: {self.source_path}")

        rasters = []
        for raster_path in self.source_path.rglob("*"):
            if raster_path.is_file() and raster_path.suffix.lower() in RASTER_EXTENSIONS:
                rasters.append(str(raster_path))
        return sorted(rasters)

    def find_rasters_s3(self) -> list[str]:
        """Find all raster files in S3 prefix recursively."""
        listing_prefix = f"{self.prefix}/" if self.prefix else ""
        rasters = []
        for chunk in obs.list(self.source_store, prefix=listing_prefix):
            for item in chunk:
                path = PurePosixPath(item["path"])
                if path.suffix.lower() in RASTER_EXTENSIONS:
                    rasters.append(
                        build_s3_uri(self.source_bucket, item["path"])
                    )
        return sorted(rasters)

    def create_vrt(self) -> Path:
        """Create a georeferenced VRT mosaic from source rasters."""
        import rasterio
        from rasterio.vrt import build_vrt
        
        if self.is_local:
            rasters = self.find_rasters_local()
        else:
            rasters = self.find_rasters_s3()

        if not rasters:
            source_description = (
                self.source_path
                if self.is_local
                else f"s3://{self.source_bucket}/{self.prefix}"
            )
            raise FileNotFoundError(f"No raster files found in: {source_description}")

        print(f"Found {len(rasters)} raster file(s)")
        for index, raster in enumerate(rasters[:5], start=1):
            print(f"  {index}. {raster}")
        if len(rasters) > 5:
            print(f"  ... and {len(rasters) - 5} more")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nCreating VRT file: {self.output_path}")

        try:
            vrt = build_vrt(
                rasters,
                src_nodata=self.no_data,
                vrt_nodata=self.no_data,
            )
            with rasterio.open(self.output_path, 'w', **vrt.profile) as dst:
                dst.write(vrt.read())
        except Exception as error:
            raise ValueError(f"Failed to create VRT file: {error}") from error

        print("VRT file created successfully")
        return self.output_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        help="Local folder path or S3 prefix to search for raster files",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path for the output VRT file",
    )
    parser.add_argument(
        "--source-bucket",
        default=SOURCE_BUCKET,
        help=f"Bucket for relative S3 prefixes (default: {SOURCE_BUCKET})",
    )
    parser.add_argument(
        "--aws-region",
        default=AWS_REGION,
        help=f"AWS region for S3 access (default: {AWS_REGION})",
    )
    parser.add_argument(
        "--no-data",
        default=0,
        help="NoData value for every input and VRT band (default: 0)",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    builder = VrtBuilder(
        source=arguments.source,
        output_path=arguments.output,
        source_bucket=arguments.source_bucket,
        aws_region=arguments.aws_region,
        no_data=arguments.no_data,
    )
    vrt_path = builder.create_vrt()
    print(f"\nOutput: {vrt_path}")


if __name__ == "__main__":
    main()
