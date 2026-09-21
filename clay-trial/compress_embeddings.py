"""Compress large embedding files for easier download."""

from download_large_file import compress_file
from pathlib import Path

# Find and compress all large .tif files in embeddings directories
embedding_dirs = [
    "data/nz_imagery_hres_embeddings/hutt-city_2021_0.075m",
    "data/nz_imagery_hres_embeddings/hutt-city_2025_0.075m",
]

for dir_path in embedding_dirs:
    dir_path = Path(dir_path)
    if not dir_path.exists():
        continue
    
    for tif_file in dir_path.rglob("*.tif"):
        size_mb = tif_file.stat().st_size / (1024 * 1024)
        if size_mb > 10:  # Only compress files larger than 10MB
            print(f"\n{'=' * 60}")
            print(f"File: {tif_file.relative_to('.')}")
            print(f"Size: {size_mb:.2f} MB")
            print(f"{'=' * 60}")
            compress_file(tif_file)

print("\n✓ All large files compressed!")
