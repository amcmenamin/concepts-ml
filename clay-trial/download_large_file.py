"""Download large files with compression and chunking."""

import gzip
import shutil
from pathlib import Path


def compress_file(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Compress a file with gzip.
    
    Args:
        input_path: Path to input file
        output_path: Path for compressed output (default: input_path.gz)
    
    Returns:
        Path to compressed file
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_suffix(input_path.suffix + ".gz")
    else:
        output_path = Path(output_path)
    
    print(f"Compressing {input_path.name}...")
    with open(input_path, "rb") as f_in:
        with gzip.open(output_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    original_size = input_path.stat().st_size / (1024 * 1024)
    compressed_size = output_path.stat().st_size / (1024 * 1024)
    ratio = (1 - compressed_size / original_size) * 100
    
    print(f"Original: {original_size:.2f} MB")
    print(f"Compressed: {compressed_size:.2f} MB")
    print(f"Saved: {ratio:.1f}%")
    print(f"Output: {output_path}")
    
    return output_path


def split_file(input_path: str | Path, chunk_size_mb: int = 20) -> list[Path]:
    """Split a file into smaller chunks.
    
    Args:
        input_path: Path to input file
        chunk_size_mb: Size of each chunk in MB (default: 20)
    
    Returns:
        List of chunk file paths
    """
    input_path = Path(input_path)
    chunk_size = chunk_size_mb * 1024 * 1024
    chunks = []
    
    print(f"Splitting {input_path.name} into {chunk_size_mb}MB chunks...")
    
    with open(input_path, "rb") as f:
        chunk_num = 0
        while True:
            chunk_data = f.read(chunk_size)
            if not chunk_data:
                break
            
            chunk_path = input_path.with_suffix(f".part{chunk_num:03d}")
            chunk_path.write_bytes(chunk_data)
            chunks.append(chunk_path)
            print(f"  Created {chunk_path.name} ({len(chunk_data) / (1024 * 1024):.2f} MB)")
            chunk_num += 1
    
    print(f"Created {len(chunks)} chunks")
    return chunks


if __name__ == "__main__":
    # Example: Compress a large embedding file
    file_to_compress = "data/nz_imagery_hres_embeddings/hutt-city_2021_0.075m/hutt-city_2021_0.075m/embeddings_highres.tif"
    
    if Path(file_to_compress).exists():
        compress_file(file_to_compress)
    else:
        print(f"File not found: {file_to_compress}")
