"""Export capture-area GeoJSON files from a LINZ imagery folder."""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path, PurePosixPath

import geopandas as gpd
import obstore as obs
import pandas as pd

from resample_aws_imagery import (
    AWS_REGION,
    SOURCE_BUCKET,
    LinzRasterProcessor,
    build_s3_uri,
    get_public_store,
    is_absolute_local_path,
    parse_s3_path,
)

CAPTURE_AREA_FILENAME = "capture-area.geojson"
COLLECTION_PATTERN = re.compile(
    r"^(?P<location>.+?)(?:_snc?\d+)?_"
    r"(?P<basedate>\d{4}(?:-\d{4})?)_"
    r"(?P<gsd>\d+(?:\.\d+)?)m$"
)


class CaptureAreaExporter:
    """Find and export capture-area files beneath a public S3 prefix.

    Files retain their full source key beneath the output location, preventing
    identically named capture-area files from overwriting one another.
    """

    def __init__(
        self,
        source: str,
        output_location: str,
        *,
        filename: str = CAPTURE_AREA_FILENAME,
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
        self.filename = filename
        self.aws_region = aws_region
        self.source_store = get_public_store(self.source_bucket, aws_region)

    def find_capture_areas(self) -> list[str]:
        """Return matching object keys recursively beneath the source prefix."""
        listing_prefix = f"{self.prefix}/" if self.prefix else ""
        return sorted(
            item["path"]
            for chunk in obs.list(self.source_store, prefix=listing_prefix)
            for item in chunk
            if PurePosixPath(item["path"]).name == self.filename
        )

    def export(self) -> list[str]:
        """Download every discovered capture-area file and return its S3 URI."""
        capture_areas = self.find_capture_areas()
        for index, key in enumerate(capture_areas, start=1):
            source_uri = build_s3_uri(self.source_bucket, key)
            print(f"[{index}/{len(capture_areas)}] Exporting {source_uri}")
            LinzRasterProcessor(
                path=source_uri,
                output_location=self.output_location,
                aws_region=self.aws_region,
            ).download_file()
        return [build_s3_uri(self.source_bucket, key) for key in capture_areas]

    @staticmethod
    def parse_collection_name(collection: str) -> tuple[str, str, float]:
        """Return location, base date, and GSD parsed from a collection folder."""
        match = COLLECTION_PATTERN.fullmatch(collection)
        if match is None:
            raise ValueError(
                "Collection folder must end with _YYYY_GSDm or "
                f"_YYYY-YYYY_GSDm: {collection}"
            )
        return (
            match.group("location"),
            match.group("basedate"),
            float(match.group("gsd")),
        )

    @property
    def hierarchy_root(self) -> Path:
        """Return the local directory corresponding to the searched S3 prefix."""
        return self.output_root.joinpath(*PurePosixPath(self.prefix).parts)

    def build_geoparquet(
        self, output_path: str | Path | None = None
    ) -> tuple[Path, int]:
        """Combine downloaded capture areas and write a GeoParquet dataset."""
        capture_area_paths = sorted(self.hierarchy_root.rglob(self.filename))
        if not capture_area_paths:
            raise FileNotFoundError(
                f"No {self.filename} files found beneath {self.hierarchy_root}"
            )

        frames: list[gpd.GeoDataFrame] = []
        target_crs = None
        for capture_area_path in capture_area_paths:
            relative_path = capture_area_path.relative_to(self.hierarchy_root)
            if len(relative_path.parts) != 4:
                raise ValueError(
                    "Capture-area path must have location/image_type/crs/file "
                    f"beneath {self.hierarchy_root}: {capture_area_path}"
                )
            collection, image_type, crs, _filename = relative_path.parts
            location, basedate, gsd = self.parse_collection_name(collection)
            frame = gpd.read_file(capture_area_path)
            if frame.crs is None:
                raise ValueError(f"Capture-area file has no CRS: {capture_area_path}")
            if target_crs is None:
                target_crs = frame.crs
            elif frame.crs != target_crs:
                frame = frame.to_crs(target_crs)

            frame["collection"] = collection
            frame["location"] = location
            frame["basedate"] = basedate
            frame["GSD"] = gsd
            frame["image_type"] = image_type
            frame["crs"] = crs
            source_key = str(PurePosixPath(self.prefix, *relative_path.parts))
            frame["s3_path"] = build_s3_uri(self.source_bucket, source_key)
            frames.append(frame)

        combined = gpd.GeoDataFrame(
            pd.concat(frames, ignore_index=True),
            geometry="geometry",
            crs=target_crs,
        )
        geoparquet_path = (
            Path(output_path).expanduser()
            if output_path is not None
            else self.output_root / "capture_areas.parquet"
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
        help="Absolute local export directory",
    )
    parser.add_argument(
        "--geoparquet",
        type=Path,
        help="Output GeoParquet path (default: OUTPUT/capture_areas.parquet)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Build GeoParquet from files already present beneath OUTPUT",
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
    exporter = CaptureAreaExporter(
        source=arguments.source,
        output_location=arguments.output_location,
        source_bucket=arguments.source_bucket,
        aws_region=arguments.aws_region,
    )
    exported = [] if arguments.skip_download else exporter.export()
    geoparquet_path, feature_count = exporter.build_geoparquet(arguments.geoparquet)
    elapsed_seconds = time.perf_counter() - start_time
    if not arguments.skip_download:
        print(f"Downloaded {len(exported)} capture-area file(s)")
    print(f"Wrote {feature_count} feature(s) to {geoparquet_path}")
    print(f"Completed in {elapsed_seconds:.3f} seconds")


if __name__ == "__main__":
    main()