from clay_tile_highres_processor import HighResClayProcessor
from pathlib import Path


# Hutt City 2021 imagery
images_2021 = [
    f"data/nz_imagery/hutt-city_2021_0.075m/BQ32_500_{tile}_0.3m.tiff"
    for tile in [
        "027025", "027026", "027027", "027028",
        "028025", "028026", "028027", "028028",
        "029023", "029024", "029025", "029026", "029027", "029028",
        "030023", "030024", "030025", "030026", "030027", "030028",
        "031023", "031024", "031025", "031026", "031027", "031028",
    ]
]

images_2021 = [
    f"data/nz_imagery/hutt-city_2021_0.075m/BQ32_500_{tile}_0.3m.tiff"
    for tile in [
        "027026",
    ]
]

# Hutt City 2025 imagery
images_2025 = [
    f"data/nz_imagery/hutt-city_2025_0.075m/BQ32_500_{tile}_0.3m.tiff"
    for tile in [
        "027025", "027026", "027027", "027028",
        "028025", "028026", "028027", "028028",
        "029023", "029024", "029025", "029026", "029027", "029028",
        "030023", "030024", "030025", "030026", "030027", "030028",
        "031023", "031024", "031025", "031026", "031027", "031028",
    ]
]

processor = HighResClayProcessor(
    checkpoint_path="clay-v1.5.ckpt",
    metadata_path="configs/metadata.yaml",
    tile_size=256,
    stride=64
)

# Choose which dataset to process
IMAGES_TO_PROCESS = images_2025  # Change to images_2021 or images_2025 as needed

for img_path in IMAGES_TO_PROCESS:
    img = Path(img_path)
    # Create output dir: data/nz_imagery_embeddings/hutt-city_2021_0.075m/BQ32_500_027025_0.3m/
    output_dir = Path("data/nz_imagery_hres_embeddings") / img.parent.name / img.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "embeddings_highres.tif"
    processor.process_image(img_path, output_path)

print(f"\nAll {len(IMAGES_TO_PROCESS)} images processed!")
