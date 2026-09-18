"""Create VRT files for multiple raster folders."""

from __future__ import annotations

import time

from create_vrt import VrtBuilder

# Configure one or more folders to create VRTs from.
# Each entry is a dict with:
#   - source: Local folder path or S3 prefix
#   - output: Output VRT file path
VRT_CONFIGS = [
    {
        "source": r"C:\Data\clay\wellington\imagery\wellington\hutt-city_2025_0.075m\rgb\2193",
        "output": r"C:\Data\clay\wellington\imagery\wellington\hutt-city_2025_0.075m\rgb\2193\hutt-city_2025_0.075m.vrt",
    },
    {
            "source": r"C:\Data\clay\wellington\imagery\wellington\hutt-city_2021_0.075m\rgb\2193",
            "output": r"C:\Data\clay\wellington\imagery\wellington\hutt-city_2021_0.075m\rgb\2193\hutt-city_2025_0.075m.vrt",
    },
    # Add more VRT configs as needed:
    # {
    #     "source": "s3://nz-imagery/wellington/hutt-city_2025_0.075m/rgb/2193",
    #     "output": r"C:\Data\clay\wellington\hutt-city_2025_0.075m.vrt",
    # },
]


def main() -> None:
    start_time = time.perf_counter()
    successful = 0
    failed = 0

    for index, config in enumerate(VRT_CONFIGS, start=1):
        print(f"\n[{index}/{len(VRT_CONFIGS)}] Creating VRT for {config['source']}")
        try:
            builder = VrtBuilder(
                source=config["source"],
                output_path=config["output"],
            )
            vrt_path = builder.create_vrt()
            successful += 1
            print(f"  ✓ VRT saved to {vrt_path}")
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
