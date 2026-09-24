"""Run automatic SAM segmentation for one GeoTIFF or a folder of GeoTIFFs."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from time import perf_counter

from segment_geotiff_automatic import SegmentGeotiffAutomatic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input GeoTIFF or folder of GeoTIFFs")
    parser.add_argument(
        "output",
        type=Path,
        help="Output GeoTIFF for one input, or output folder for folder input",
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--model-type", choices=("vit_h", "vit_l", "vit_b"), default="vit_b")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--points-per-side", type=int, default=32)
    parser.add_argument("--pred-iou-thresh", type=float, default=0.88)
    parser.add_argument("--stability-score-thresh", type=float, default=0.95)
    parser.add_argument("--crop-n-layers", type=int, default=1)
    parser.add_argument(
        "--min-mask-region-area",
        type=int,
        default=100,
    )
    parser.add_argument(
        "--append-parameters",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Append SAM parameters to output filenames (default: enabled)",
    )
    parser.add_argument(
        "--vector-output",
        type=Path,
        help="Optional vector output for one image, or vector output folder for folder input",
    )
    return parser.parse_args()


def image_files(folder: Path) -> list[Path]:
    return sorted(
        path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
    )


def segment_image(
    segmenter: SegmentGeotiffAutomatic,
    image_path: Path,
    output_path: Path,
    vector_output_path: Path | None = None,
) -> None:
    start_time = datetime.now().astimezone()
    start_counter = perf_counter()
    print(f"Start time: {start_time.isoformat(timespec='seconds')} | Image: {image_path}")
    segmenter.segment(image_path, output_path, vector_output_path)
    end_time = datetime.now().astimezone()
    elapsed_seconds = perf_counter() - start_counter
    elapsed_minutes = elapsed_seconds / 60
    print(
        f"End time: {end_time.isoformat(timespec='seconds')} | "
        f"Elapsed: {elapsed_seconds:.1f}s ({elapsed_minutes:.1f} minutes) | "
        f"Image: {image_path}"
    )


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(args.input)

    segmenter = SegmentGeotiffAutomatic(
        checkpoint=args.checkpoint,
        model_type=args.model_type,
        device=args.device,
        points_per_side=args.points_per_side,
        pred_iou_thresh=args.pred_iou_thresh,
        stability_score_thresh=args.stability_score_thresh,
        crop_n_layers=args.crop_n_layers,
        min_mask_region_area=args.min_mask_region_area,
        append_parameters=args.append_parameters,
    )

    if args.input.is_file():
        segment_image(segmenter, args.input, args.output, args.vector_output)
        return

    files = image_files(args.input)
    if not files:
        raise FileNotFoundError(f"No .tif or .tiff files found in {args.input}")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.vector_output is not None:
        args.vector_output.mkdir(parents=True, exist_ok=True)
    for image_path in files:
        vector_output_path = None
        if args.vector_output is not None:
            vector_output_path = args.vector_output / f"{image_path.stem}.gpkg"
        segment_image(segmenter, image_path, args.output / image_path.name, vector_output_path)


if __name__ == "__main__":
    main()