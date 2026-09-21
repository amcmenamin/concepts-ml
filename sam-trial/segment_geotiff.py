"""Create a georeferenced SAM 2.1 mask from a GeoTIFF and a point prompt."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from ultralytics import SAM


def parse_point(value: str) -> tuple[int, int]:
    try:
        x_text, y_text = value.split(",", maxsplit=1)
        return int(x_text), int(y_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("point must use x,y pixel coordinates") from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Input GeoTIFF")
    parser.add_argument("output", type=Path, help="Output mask GeoTIFF")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--prompt-point", type=parse_point, required=True)
    parser.add_argument("--device", default="cpu", help="Inference device (default: cpu)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.image.is_file():
        raise FileNotFoundError(args.image)
    if not args.checkpoint.is_file():
        raise FileNotFoundError(args.checkpoint)

    with rasterio.open(args.image) as source:
        image = source.read()
        profile = source.profile.copy()

    if image.shape[0] < 3:
        raise ValueError("SAM requires an image with at least three bands")
    image = np.moveaxis(image[:3], 0, -1)
    image = np.clip(image, 0, 255).astype(np.uint8)

    point_x, point_y = args.prompt_point
    if not (0 <= point_x < image.shape[1] and 0 <= point_y < image.shape[0]):
        raise ValueError("--prompt-point is outside the image dimensions")

    model = SAM(str(args.checkpoint))
    results = model.predict(
        source=image,
        points=[[point_x, point_y]],
        labels=[1],
        device=args.device,
        verbose=False,
    )
    if not results or results[0].masks is None:
        raise RuntimeError("SAM did not return a mask for the prompt")

    mask = results[0].masks.data[0].cpu().numpy().astype(np.uint8)
    profile.update(driver="GTiff", count=1, dtype="uint8", nodata=0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.output, "w", **profile) as destination:
        destination.write(mask, 1)

    print(f"Wrote mask: {args.output}")


if __name__ == "__main__":
    main()