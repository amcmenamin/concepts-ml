"""Create VRT files for multiple raster folders."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path


VRT_CONFIGS_AWS = [
    {
        "source": "/home/sagemaker-user/concepts-ml/clay-trial/data/nz_imagery/hutt-city_2021_0.075m",
        "output": "/home/sagemaker-user/concepts-ml/clay-trial/data/nz_imagery/hutt-city_2021_0.075m/hutt-city_2021_0.075m.vrt",
    },
    {
        "source": "/home/sagemaker-user/concepts-ml/clay-trial/data/nz_imagery/hutt-city_2025_0.075m",
        "output": "/home/sagemaker-user/concepts-ml/clay-trial/data/nz_imagery/hutt-city_2025_0.075m/hutt-city_2025_0.075m.vrt",
    },
]

VRT_CONFIGS = VRT_CONFIGS_AWS

def main() -> None:
    start_time = time.perf_counter()
    successful = 0
    failed = 0

    for index, config in enumerate(VRT_CONFIGS, start=1):
        source = Path(config["source"])
        output = Path(config["output"])
        
        print(f"\n[{index}/{len(VRT_CONFIGS)}] Creating VRT for {source}")
        
        try:
            # Find all tiff files
            tiff_files = sorted(source.glob("*.tiff")) + sorted(source.glob("*.tif"))
            
            if not tiff_files:
                raise FileNotFoundError(f"No TIFF files found in {source}")
            
            print(f"  Found {len(tiff_files)} TIFF file(s)")
            
            # Create output directory
            output.parent.mkdir(parents=True, exist_ok=True)
            
            # Build gdalbuildvrt command
            cmd = ["gdalbuildvrt", str(output)] + [str(f) for f in tiff_files]
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise RuntimeError(f"gdalbuildvrt failed: {result.stderr}")
            
            successful += 1
            print(f"  ✓ VRT saved to {output}")
            
        except Exception as e:
            failed += 1
            print(f"  ✗ Failed: {e}")

    elapsed_seconds = time.perf_counter() - start_time
    print(f"\n{'=' * 60}")
    print(f"Successfully created: {successful} VRT file(s)")
    if failed > 0:
        print(f"Failed: {failed}")
    print(f"Completed in {elapsed_seconds:.3f} seconds")


if __name__ == "__main__":
    main()
