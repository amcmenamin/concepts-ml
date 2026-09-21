"""Run high-resolution Clay embedding processing on raster images."""

from clay_tile_highres_processor import HighResClayProcessor

# Configuration
CHECKPOINT = "clay-v1.5.ckpt"
METADATA = "configs/metadata.yaml"
TILE_SIZE = 256
STRIDE = 64  # 64 * 0.075m = 4.8m resolution

# Images to process
IMAGES = [
    {
        "input": "data/AY30_1000_4448.tiff",
        "output": "data/AY30_1000_4448/embeddings_highres.tif",
    },
    # Add more images as needed
]

def main() -> None:
    processor = HighResClayProcessor(
        checkpoint_path=CHECKPOINT,
        metadata_path=METADATA,
        tile_size=TILE_SIZE,
        stride=STRIDE,
    )

    for config in IMAGES:
        print(f"\n{'=' * 60}")
        print(f"Processing: {config['input']}")
        print(f"{'=' * 60}")
        processor.process_image(
            input_path=config["input"],
            output_path=config["output"],
        )

    print(f"\n{'=' * 60}")
    print(f"All {len(IMAGES)} image(s) processed successfully!")


if __name__ == "__main__":
    main()
