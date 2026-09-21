"""Generate automatic SAM instance masks for a GeoTIFF.

This uses Meta's original ``segment-anything`` package. Its checkpoint must
be a compatible SAM checkpoint, such as ``sam_vit_b_01ec64.pth``; an
Ultralytics SAM 2.1 checkpoint is not interchangeable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from segment_anything import SamAutomaticMaskGenerator, sam_model_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Input RGB GeoTIFF")
    parser.add_argument("output", type=Path, help="Output instance-label GeoTIFF")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--model-type",
        choices=("vit_h", "vit_l", "vit_b"),
        default="vit_b",
        help="SAM checkpoint architecture (default: vit_b)",
    )
    parser.add_argument("--device", default="cpu", help="Inference device (default: cpu)")
    parser.add_argument("--points-per-side", type=int, default=32)
    parser.add_argument("--pred-iou-thresh", type=float, default=0.88)
    parser.add_argument("--stability-score-thresh", type=float, default=0.95)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.image.is_file():
        raise FileNotFoundError(args.image)
    if not args.checkpoint.is_file():
        raise FileNotFoundError(args.checkpoint)

    with rasterio.open(args.image) as source:
        bands = source.read()
        profile = source.profile.copy()

    if bands.shape[0] < 3:
        raise ValueError("SAM requires an image with at least three bands")
    image = np.moveaxis(bands[:3], 0, -1)
    image = np.clip(image, 0, 255).astype(np.uint8)

    sam = sam_model_registry[args.model_type](checkpoint=str(args.checkpoint))
    sam.to(device=args.device)
    mask_generator = SamAutomaticMaskGenerator(
        model=sam,
        points_per_side=args.points_per_side,
        pred_iou_thresh=args.pred_iou_thresh,
        stability_score_thresh=args.stability_score_thresh,
    )
    masks = mask_generator.generate(image)
    if len(masks) > np.iinfo(np.uint16).max:
        raise ValueError("SAM returned more than 65,535 masks; reduce --points-per-side")

    # Smaller regions are written last so they remain visible inside larger masks.
    masks.sort(key=lambda item: int(item["area"]), reverse=True)
    labelled = np.zeros(image.shape[:2], dtype=np.uint16)
    for mask_id, mask_data in enumerate(masks, start=1):
        labelled[mask_data["segmentation"]] = mask_id

    profile.update(driver="GTiff", count=1, dtype="uint16", nodata=0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.output, "w", **profile) as destination:
        destination.write(labelled, 1)

    print(f"Wrote {len(masks)} instance masks: {args.output}")


if __name__ == "__main__":
    main()