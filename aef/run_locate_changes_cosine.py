import time
from pathlib import Path

from locate_changes_cosine import CosineChangeDetector


CHANGES = [
    {
        "earlier": Path(
            r"C:\Data\AEF\wanaka\2019\xkmgcxnihpzce8az1-0000008192-0000000000.tiff"
        ),
        "later": Path(
            r"C:\Data\AEF\wanaka\2024\xd8jjxuf7h0qy40py-0000008192-0000000000.tiff"
        ),
        "output_directory": Path(
            r"C:\Data\AEF\wanaka\change_detection\2019_to_2024"
        ),
        "percentile": 95.0,
        "block_size": 512,
    },
]


def main() -> None:
    start_time = time.perf_counter()

    for index, change in enumerate(CHANGES, start=1):
        print(
            f"[{index}/{len(CHANGES)}] Comparing "
            f"{change['earlier']} to {change['later']}"
        )
        detector = CosineChangeDetector(
            earlier_path=change["earlier"],
            later_path=change["later"],
            output_directory=change["output_directory"],
            percentile=change["percentile"],
            block_size=change["block_size"],
        )
        score_path, mask_path, threshold, score_percentiles = detector.run()

        print(f"Change-score raster: {score_path}")
        print(f"Change mask: {mask_path}")
        print(f"Cosine-distance threshold: {threshold:.5f}")
        print("Change-score percentiles:")
        for percentile, score in score_percentiles.items():
            print(f"  {percentile:>2}th: {score:.5f}")

    elapsed_seconds = time.perf_counter() - start_time
    print(f"Completed {len(CHANGES)} comparison(s) in {elapsed_seconds:.3f} seconds")


if __name__ == "__main__":
    main()