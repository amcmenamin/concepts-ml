"""Generate georeferenced masks from a GeoTIFF with SAM 3 text prompts."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("image", type=Path, help="Input GeoTIFF or image path")
	parser.add_argument("prompt", help="Object or class to segment, such as 'water'")
	parser.add_argument("output", type=Path, help="Output mask GeoTIFF path")
	parser.add_argument(
		"--checkpoint",
		type=Path,
		default=Path(__file__).with_name("sam3.pt"),
		help="Local SAM 3 checkpoint (default: sam-trial/sam3.pt)",
	)
	parser.add_argument(
		"--tile-size",
		type=int,
		help="Tile size in pixels for large images; omit for whole-image inference",
	)
	parser.add_argument(
		"--overlap",
		type=int,
		default=128,
		help="Tile overlap in pixels (default: 128)",
	)
	parser.add_argument(
		"--min-size",
		type=int,
		default=100,
		help="Discard objects smaller than this many pixels in tiled mode",
	)
	parser.add_argument(
		"--unique",
		action="store_true",
		help="Write a unique integer label for each detected object",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()

	if not args.image.is_file():
		raise FileNotFoundError(f"Input image does not exist: {args.image}")
	if not args.checkpoint.is_file():
		raise FileNotFoundError(f"SAM 3 checkpoint does not exist: {args.checkpoint}")
	if args.tile_size is not None and args.tile_size <= args.overlap:
		raise ValueError("--tile-size must be greater than --overlap")

	from samgeo import SamGeo3

	sam = SamGeo3(
		backend="meta",
		checkpoint_path=str(args.checkpoint),
		load_from_HF=False,
	)

	if args.tile_size is None:
		sam.set_image(str(args.image))
		sam.generate_masks(prompt=args.prompt)
		sam.save_masks(output=str(args.output), unique=args.unique)
	else:
		sam.generate_masks_tiled(
			source=str(args.image),
			prompt=args.prompt,
			output=str(args.output),
			tile_size=args.tile_size,
			overlap=args.overlap,
			min_size=args.min_size,
			unique=args.unique,
			dtype="int32",
			verbose=True,
		)

	print(f"Wrote mask: {args.output}")


if __name__ == "__main__":
	main()

