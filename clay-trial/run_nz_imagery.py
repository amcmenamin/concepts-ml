from clay_tile_processor import ClayTileProcessor
from pathlib import Path

images = [
    "data/nz_imagery/BQ32_1000_1101_1_0.3m.tiff",
    "data/nz_imagery/BQ32_1000_1101_2_0.3m.tiff",
    "data/nz_imagery/BQ32_500_021001_0.3m.tiff",
    "data/nz_imagery/BQ32_500_021002_0.3m.tiff",
]

# cls create single value per tile (global summary) - small file output
processor = ClayTileProcessor(embedding_mode="cls")

# patches create embeddings for all patches within each tile - larger file output
# processor = ClayTileProcessor(embedding_mode="patches")

output_dir = Path("data/nz_imagery_output")
output_dir.mkdir(parents=True, exist_ok=True)
for img in images:
    processor.process_image(img, output_dir=output_dir)

print("\nAll images processed!")
