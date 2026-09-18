import time
from datetime import datetime
from pathlib import Path

from resample_aws_imagery import (
    DEFAULT_LOG_FILE,
    TARGET_RESOLUTION,
    LinzRasterProcessor,
    close_logging,
    configure_logging,
    logger,
)

OUTPUT_LOCATION = Path(r"C:\Data\clay\wellington\imagery")
LOG_FILE = OUTPUT_LOCATION / DEFAULT_LOG_FILE

INPUTS = [
    "s3://nz-imagery/wellington/wellington_2016-2017_0.3m/rgb/2193/BR34_5000_0302.tiff",
    "s3://nz-imagery/wellington/wellington_2017_0.1m/rgb/2193/BQ32_500_021001.tiff",
    "s3://nz-imagery/wellington/wellington_2012-2013_0.3m/rgb/2193/BR34_5000_0302.tiff",
    "s3://nz-imagery/wellington/wellington_2012-2013_0.1m/rgb/2193/BQ32_500_021001.tiff",
    "s3://nz-imagery/wellington/wellington_2021_0.3m/rgb/2193/BR34_5000_0302.tiff",
    "s3://nz-imagery/wellington/wellington_2021_0.075m/rgb/2193/BQ32_500_022002.tiff",
    "s3://nz-imagery/wellington/wellington_2024_0.25m/rgb/2193/BR34_5000_0401.tiff",
    "s3://nz-imagery/wellington/wellington_2025_0.2m/rgb/2193/BR34_5000_0302.tiff",
    "s3://nz-imagery/wellington/wellington_2025_0.075m/rgb/2193/BQ32_1000_1101.tiff",
]

INPUTS =[
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_1000_0224.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_1000_0124.tiff",
]

INPUTS = [
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_027025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_027026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_027027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_027028.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_028025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_028026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_028027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_028028.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_029023.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_029024.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_029025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_029026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_029027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_029028.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_030023.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_030024.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_030025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_030026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_030027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_030028.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_031023.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_031024.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_031025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_031026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_031027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193/BQ32_500_031028.tiff",
]

INPUTS = [
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_027025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_027026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_027027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_027028.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_028025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_028026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_028027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_028028.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_029023.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_029024.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_029025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_029026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_029027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_029028.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_030023.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_030024.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_030025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_030026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_030027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_030028.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_031023.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_031024.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_031025.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_031026.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_031027.tiff",
    "s3://nz-imagery/wellington/hutt-city_2021_0.075m/rgb/2193/BQ32_500_031028.tiff",
]


def run_phase(*, raw: bool) -> None:
    phase = "raw download" if raw else f"{TARGET_RESOLUTION:g}m resample"
    logger.info("Starting %s phase for %d images", phase, len(INPUTS))

    for index, source in enumerate(INPUTS, start=1):
        logger.info("[%d/%d] %s", index, len(INPUTS), source)
        processor = LinzRasterProcessor(
            path=source,
            output_location=str(OUTPUT_LOCATION),
            raw=raw,
            target_resolution=TARGET_RESOLUTION,
        )
        processor.process()


def main(run_raw: bool, run_resample: bool) -> None:
    configure_logging(str(LOG_FILE))
    start_time = datetime.now().astimezone()
    start_counter = time.perf_counter()
    logger.info("Batch start time: %s", start_time.isoformat())
    logger.info("Output location: %s", OUTPUT_LOCATION)
    logger.info("Log file: %s", LOG_FILE)

    try:
        if run_raw:
            run_phase(raw=True)
        if run_resample:
            run_phase(raw=False)
    except Exception:
        logger.exception("Batch processing failed")
        raise
    finally:
        end_time = datetime.now().astimezone()
        elapsed_seconds = time.perf_counter() - start_counter
        logger.info("Batch end time: %s", end_time.isoformat())
        logger.info("Batch processing time: %.3f seconds", elapsed_seconds)
        close_logging()


if __name__ == "__main__":
    main(run_raw=False, run_resample=True)
