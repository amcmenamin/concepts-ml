import argparse
import logging
import time
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlparse

import obstore as obs
from obstore.store import S3Store
from rasterio.enums import Resampling
from rasterio.io import MemoryFile

SOURCE_BUCKET = "nz-imagery"
AWS_REGION = "ap-southeast-2"
TARGET_RESOLUTION = 0.3
DEFAULT_LOG_FILE = "resample_aws_imagery.log"

logger = logging.getLogger(__name__)


def is_absolute_local_path(location: str) -> bool:
    return location.startswith("/") or PureWindowsPath(location).is_absolute()


def resolve_log_file(
    log_file: str | None,
    output_location: str | None,
    default_log_file: str = DEFAULT_LOG_FILE,
) -> str:
    if log_file:
        return log_file
    if output_location and is_absolute_local_path(output_location):
        return str(Path(output_location).expanduser() / default_log_file)
    return default_log_file


def configure_logging(log_file: str) -> None:
    log_path = Path(log_file).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False


def close_logging() -> None:
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


def get_public_store(
    bucket: str = SOURCE_BUCKET,
    region: str = AWS_REGION,
) -> S3Store:
    return S3Store(bucket=bucket, region=region, skip_signature=True)


def get_output_store(bucket: str, region: str = AWS_REGION) -> S3Store:
    return S3Store(bucket=bucket, region=region)


def parse_s3_path(
    path: str,
    source_bucket: str = SOURCE_BUCKET,
    aws_region: str = AWS_REGION,
) -> tuple[str, str]:
    path = path.strip()
    if path.startswith(("http://", "https://")):
        parsed = urlparse(path)
        expected_host = f"s3.{aws_region}.amazonaws.com"
        if parsed.scheme != "https" or parsed.netloc != expected_host:
            raise ValueError(
                f"HTTPS source must use https://{expected_host}/bucket/path"
            )
        bucket, separator, key = parsed.path.lstrip("/").partition("/")
        if not bucket or not separator or not key:
            raise ValueError("HTTPS S3 path must include a bucket and object path")
        return bucket, key

    if not path.startswith("s3://"):
        return source_bucket, path.lstrip("/")

    parsed = urlparse(path)
    if not parsed.netloc:
        raise ValueError("S3 path must include a bucket name")
    return parsed.netloc, parsed.path.lstrip("/")


def build_s3_uri(bucket: str, path: str) -> str:
    return f"s3://{bucket}/{path}"


def build_http_url(bucket: str, path: str, region: str = AWS_REGION) -> str:
    """Build an HTTPS URL for public S3 object access."""
    return f"https://s3.{region}.amazonaws.com/{bucket}/{path}"


class OutputDestination:
    def __init__(self, location: str, aws_region: str = AWS_REGION) -> None:
        self.location = location.strip()
        self.store: S3Store | None = None
        self.bucket = ""
        self.prefix = ""
        self.local_root: Path | None = None

        if self.location.startswith("s3://"):
            self.bucket, self.prefix = parse_s3_path(
                self.location,
                aws_region=aws_region,
            )
            self.prefix = self.prefix.rstrip("/")
        elif is_absolute_local_path(self.location):
            self.local_root = Path(self.location).expanduser()
        else:
            self.bucket = self.location

        if self.local_root is None:
            self.store = get_output_store(self.bucket, aws_region)

    def write(self, key: str, content: bytes) -> str:
        if self.local_root is not None:
            output_path = self.local_root.joinpath(*PurePosixPath(key).parts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)
            return str(output_path)

        output_key = "/".join(part for part in (self.prefix, key) if part)
        obs.put(self.store, output_key, content)
        return build_s3_uri(self.bucket, output_key)


def resample_raster(content: bytes, target_resolution: float) -> bytes:
    with MemoryFile(content) as source_memory_file:
        with source_memory_file.open() as dataset:
            source_crs = dataset.crs
            if source_crs is None:
                logger.warning("Input raster has no CRS")
            else:
                logger.info("Input CRS: %s", source_crs)

            gsd = abs(dataset.transform.a)
            scale_factor = gsd / target_resolution
            output_height = max(1, int(dataset.height * scale_factor))
            output_width = max(1, int(dataset.width * scale_factor))

            data = dataset.read(
                out_shape=(dataset.count, output_height, output_width),
                resampling=Resampling.bilinear,
            )[:3]

            transform = dataset.transform * dataset.transform.scale(
                dataset.width / output_width,
                dataset.height / output_height,
            )
            metadata = dataset.meta.copy()
            metadata.update(
                crs=source_crs,
                transform=transform,
                width=output_width,
                height=output_height,
                compress="deflate",
                count=3,
            )

    with MemoryFile() as output_memory_file:
        with output_memory_file.open(**metadata) as destination:
            destination.write(data)
        output = output_memory_file.read()

    return output


class LinzRasterProcessor:
    def __init__(
        self,
        path: str,
        output_location: str | None = None,
        *,
        all_imagery: bool = False,
        raw: bool = False,
        target_resolution: float = TARGET_RESOLUTION,
        source_bucket: str = SOURCE_BUCKET,
        aws_region: str = AWS_REGION,
    ) -> None:
        if target_resolution <= 0:
            raise ValueError("Target resolution must be greater than zero")
        source = path.strip()
        self.local_source: Path | None = None
        if source.startswith("/") or PureWindowsPath(source).is_absolute():
            self.local_source = Path(source).expanduser()
            self.source_bucket = ""
            self.path = str(self.local_source)
        else:
            self.source_bucket, self.path = parse_s3_path(
                source,
                source_bucket=source_bucket,
                aws_region=aws_region,
            )
        self.output_location = output_location
        self.all_imagery = all_imagery
        self.raw = raw
        self.target_resolution = target_resolution
        self.aws_region = aws_region
        self.source_store = (
            None
            if self.local_source is not None
            else get_public_store(self.source_bucket, self.aws_region)
        )

    def list_files(self, url_format: str = "s3") -> list[str]:
        prefix = self.path.rstrip("/") + "/"
        files = [
            item["path"]
            for chunk in obs.list(self.source_store, prefix=prefix)
            for item in chunk
        ]
        for key in files:
            if url_format in ("s3", "both"):
                print(build_s3_uri(self.source_bucket, key))
            if url_format in ("http", "both"):
                print(build_http_url(self.source_bucket, key, self.aws_region))
        logger.info(
            f"Found {len(files)} objects under "
            f"{build_s3_uri(self.source_bucket, prefix)}"
        )
        return files

    def get_tiffs(self) -> list[str]:
        if self.local_source is not None:
            if self.all_imagery:
                if not self.local_source.is_dir():
                    raise ValueError("A local folder is required with --all-imagery")
                files = sorted(
                    str(path)
                    for path in self.local_source.rglob("*")
                    if path.is_file() and path.suffix.lower() in (".tif", ".tiff")
                )
                logger.info("Found %d scenes under %s", len(files), self.local_source)
                return files

            if not self.local_source.is_file():
                raise FileNotFoundError(f"Local input image not found: {self.local_source}")
            if self.local_source.suffix.lower() not in (".tif", ".tiff"):
                raise ValueError("A local input image must end with .tif or .tiff")
            return [str(self.local_source)]

        if not self.all_imagery:
            if not self.path.lower().endswith(".tiff"):
                raise ValueError("A single-image path must end with .tiff")
            return [self.path]

        prefix = self.path.rstrip("/") + "/"
        files = [
            item["path"]
            for chunk in obs.list(self.source_store, prefix=prefix)
            for item in chunk
            if item["path"].lower().endswith(".tiff")
        ]
        logger.info("Found %d scenes under %s", len(files), prefix)
        return files

    def read_image(self, path: str) -> bytes:
        if self.local_source is not None:
            return Path(path).read_bytes()
        return bytes(obs.get(self.source_store, path).bytes())

    def read_companion_json(self, path: str) -> tuple[str, bytes] | None:
        if self.local_source is not None:
            json_path = Path(path).with_suffix(".json")
            if not json_path.is_file():
                return None
            return json_path.name, json_path.read_bytes()

        json_key = str(PurePosixPath(path).with_suffix(".json"))
        try:
            content = bytes(obs.get(self.source_store, json_key).bytes())
        except FileNotFoundError:
            return None
        return PurePosixPath(json_key).name, content

    def build_output_key(self, source_path: str, filename: str) -> str:
        if self.local_source is None:
            return str(PurePosixPath(source_path).with_name(filename))
        if self.local_source.is_dir():
            relative_path = Path(source_path).relative_to(self.local_source)
            return str(PurePosixPath(*relative_path.parts).with_name(filename))
        return filename

    def download_file(self) -> None:
        if not self.output_location:
            raise ValueError("An output location is required to download a file")
        if self.local_source is not None and not self.local_source.is_file():
            raise FileNotFoundError(f"Local input file not found: {self.local_source}")

        output = OutputDestination(self.output_location, self.aws_region)
        content = self.read_image(self.path)
        filename = (
            Path(self.path).name
            if self.local_source is not None
            else PurePosixPath(self.path).name
        )
        output_key = self.build_output_key(self.path, filename)
        output_path = output.write(output_key, content)
        logger.info("Wrote %s", output_path)

    def process(self) -> None:
        if not self.output_location:
            raise ValueError("An output location is required to process imagery")
        output = OutputDestination(self.output_location, self.aws_region)

        for key in self.get_tiffs():
            logger.info("Working on %s", key)
            raster_content = self.read_image(key)
            output_content = (
                raster_content
                if self.raw
                else resample_raster(raster_content, self.target_resolution)
            )

            filename = (
                Path(key).name
                if self.local_source is not None
                else PurePosixPath(key).name
            )
            if not self.raw:
                source_name = PurePosixPath(filename)
                filename = (
                    f"{source_name.stem}_{self.target_resolution:g}m"
                    f"{source_name.suffix}"
                )
            new_key = self.build_output_key(key, filename)
            output_path = output.write(new_key, output_content)
            logger.info("Wrote %s", output_path)

            if self.raw:
                companion_json = self.read_companion_json(key)
                if companion_json is not None:
                    json_filename, json_content = companion_json
                    json_key = self.build_output_key(key, json_filename)
                    json_output_path = output.write(json_key, json_content)
                    logger.info("Wrote %s", json_output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resample LINZ imagery using obstore")
    parser.add_argument(
        "path",
        help=(
            "Source TIFF/folder key, s3:// URI, public S3 HTTPS URL, "
            "or absolute local path"
        ),
    )
    parser.add_argument(
        "--list-files",
        action="store_true",
        help="List objects beneath the source folder without processing them",
    )
    parser.add_argument(
        "--url-format",
        choices=("s3", "http", "both"),
        default="s3",
        help="URL format printed by --list-files (default: s3)",
    )
    parser.add_argument(
        "--all-imagery",
        action="store_true",
        help="Process every TIFF beneath the source folder",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Copy source image bytes without resampling",
    )
    parser.add_argument(
        "--download-file",
        action="store_true",
        help="Copy one file without TIFF validation or raster processing",
    )
    parser.add_argument(
        "--target-resolution",
        type=float,
        default=TARGET_RESOLUTION,
        help=f"Output pixel resolution in source CRS units (default: {TARGET_RESOLUTION})",
    )
    parser.add_argument(
        "--source-bucket",
        default=SOURCE_BUCKET,
        help=f"Source bucket for bucket-relative paths (default: {SOURCE_BUCKET})",
    )
    parser.add_argument(
        "--aws-region",
        default=AWS_REGION,
        help=f"AWS region for S3 access and HTTPS URLs (default: {AWS_REGION})",
    )
    parser.add_argument(
        "--output",
        dest="output_location",
        help="Destination S3 bucket, s3:// URI, or absolute local directory",
    )
    parser.add_argument(
        "--log-file",
        help=(
            "Log file path (defaults to the local output directory, or "
            f"{DEFAULT_LOG_FILE} for S3 and listing runs)"
        ),
    )
    parser.add_argument(
        "--default-log-file",
        default=DEFAULT_LOG_FILE,
        help=f"Default log filename when --log-file is omitted (default: {DEFAULT_LOG_FILE})",
    )
    args = parser.parse_args()
    if not args.list_files and not args.output_location:
        parser.error("--output is required unless --list-files is used")
    if args.download_file and (args.list_files or args.all_imagery or args.raw):
        parser.error(
            "--download-file cannot be combined with --list-files, "
            "--all-imagery, or --raw"
        )
    return args


def main() -> None:
    args = parse_args()
    log_file = resolve_log_file(
        args.log_file,
        args.output_location,
        args.default_log_file,
    )
    configure_logging(log_file)
    start_time = datetime.now().astimezone()
    start_counter = time.perf_counter()
    logger.info("Start time: %s", start_time.isoformat())

    try:
        processor = LinzRasterProcessor(
            path=args.path,
            output_location=args.output_location,
            all_imagery=args.all_imagery,
            raw=args.raw,
            target_resolution=args.target_resolution,
            source_bucket=args.source_bucket,
            aws_region=args.aws_region,
        )
        if args.list_files:
            processor.list_files(url_format=args.url_format)
        elif args.download_file:
            processor.download_file()
        else:
            processor.process()
    except Exception:
        logger.exception("Processing failed")
        raise
    finally:
        end_time = datetime.now().astimezone()
        elapsed_seconds = time.perf_counter() - start_counter
        logger.info("End time: %s", end_time.isoformat())
        logger.info("Processing time: %.3f seconds", elapsed_seconds)
        logger.info("Output location: %s", args.output_location or "not set")
        logger.info("Log file: %s", str(Path(log_file).expanduser().resolve()))
        close_logging()


if __name__ == "__main__":
    main()