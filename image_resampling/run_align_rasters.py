import time
from pathlib import Path

from align_rasters import RasterAligner


ALIGNMENTS = [
    {
        "reference": Path(r"C:\Data\clay\wellington\imagery\wellington\wellington_2012-2013_0.1m\rgb\2193\BQ32_500_021001.tiff"),
        "input": Path(r"C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101.tiff"),
        "output": Path(r"C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101_1.tiff"),
    },
    {
        "reference": Path(r"C:\Data\clay\wellington\imagery\wellington\wellington_2021_0.075m\rgb\2193\BQ32_500_021002.tiff"),
        "input": Path(r"C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101.tiff"),
        "output": Path(r"C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101_2.tiff"),
    },
]


def main() -> None:
    start_time = time.perf_counter()

    for index, alignment in enumerate(ALIGNMENTS, start=1):
        print(
            f"[{index}/{len(ALIGNMENTS)}] Aligning "
            f"{alignment['input']} to {alignment['reference']}"
        )
        output_path = RasterAligner(
            reference_path=alignment["reference"],
            input_path=alignment["input"],
            output_path=alignment["output"],
        ).align()
        print(f"Wrote {output_path}")

    elapsed_seconds = time.perf_counter() - start_time
    print(f"Aligned {len(ALIGNMENTS)} raster(s) in {elapsed_seconds:.3f} seconds")


if __name__ == "__main__":
    main()