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

for img in images:
    processor.process_image(img)

print("\nAll images processed!")
