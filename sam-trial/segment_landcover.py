"""Create a labelled GeoTIFF from multiple SAM point prompts.

This is prompt-driven object segmentation, not a trained land-cover
classifier. Each prompt should be placed inside one object or region.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from ultralytics import SAM


def parse_prompt(value: str) -> tuple[str, int, int]:
    try:
        class_name, x_text, y_text = value.split(",", maxsplit=2)
        if not class_name.strip():
            raise ValueError
        return class_name.strip(), int(x_text), int(y_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "prompt must use class,x,y, for example vegetation,120,80"
        ) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Input GeoTIFF")
    parser.add_argument("output", type=Path, help="Output labelled GeoTIFF")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--prompt",
        type=parse_prompt,
        action="append",
        required=True,
        metavar="CLASS,X,Y",
        help="Class name and pixel prompt; repeat for each segment",
    )
    parser.add_argument("--device", default="cpu", help="Inference device (default: cpu)")
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

    model = SAM(str(args.checkpoint))
    labelled = np.zeros(image.shape[:2], dtype=np.uint8)
    class_ids: dict[str, int] = {}

    for class_name, point_x, point_y in args.prompt:
        if not (0 <= point_x < image.shape[1] and 0 <= point_y < image.shape[0]):
            raise ValueError(f"prompt point for {class_name!r} is outside the image dimensions")
        if class_name not in class_ids:
            class_ids[class_name] = len(class_ids) + 1
        results = model.predict(
            source=image,
            points=[[point_x, point_y]],
            labels=[1],
            device=args.device,
            verbose=False,
        )
        if not results or results[0].masks is None:
            raise RuntimeError(f"SAM did not return a mask for {class_name!r}")
        mask = results[0].masks.data[0].cpu().numpy().astype(bool)
        labelled[mask] = class_ids[class_name]

    profile.update(driver="GTiff", count=1, dtype="uint8", nodata=0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.output, "w", **profile) as destination:
        destination.write(labelled, 1)

    print(f"Wrote labelled mask: {args.output}")
    print("Class IDs: " + ", ".join(f"{value}={key}" for key, value in class_ids.items()))


if __name__ == "__main__":
    main()