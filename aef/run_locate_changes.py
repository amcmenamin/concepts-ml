import argparse
import time
from pathlib import Path

from locate_changes_cosine import CosineChangeDetector
from locate_changes_euclidean import detect_changes
from locate_changes_knn_novelty import detect_novelty


CHANGES = [
    {
        "earlier": Path(
            r"C:\Data\clay\wellington\embeddings\hutt-city_2021-5_0.075m-full\2021\embeddings_highres.tif"
        ),
        "later": Path(
            r"C:\Data\clay\wellington\embeddings\hutt-city_2021-5_0.075m-full\2025\embeddings_highres.tif"
        ),
        "output_directory": Path(
            r"C:\Data\clay\wellington\embeddings\change_detection\2021_to_2025"
        ),
        "percentile": 95.0,
        "block_size": 512,
    },
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AlphaEarth change detectors")
    parser.add_argument(
        "--analysis",
        choices=["all", "cosine", "euclidean", "knn"],
        default="cosine",
        help="Detector to run (default: cosine)",
    )
    return parser.parse_args()


def run_cosine(change) -> None:
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


def run_euclidean(change) -> None:
    score_path, mask_path, threshold, score_percentiles = detect_changes(
        change["earlier"],
        change["later"],
        change["output_directory"],
        change["percentile"],
        change["block_size"],
    )

    print(f"Euclidean change-score raster: {score_path}")
    print(f"Euclidean change mask: {mask_path}")
    print(f"Euclidean-distance threshold: {threshold:.5f}")
    print("Euclidean score percentiles:")
    for percentile, score in score_percentiles.items():
        print(f"  {percentile:>2}th: {score:.5f}")


def run_knn(change) -> None:
    output_path = change["output_directory"] / "knn_novelty_score.tif"
    novelty_path = detect_novelty(
        change["earlier"],
        change["later"],
        output_path,
        stride=16,
        reference_samples=10_000,
        neighbours=5,
        seed=42,
    )
    print(f"kNN novelty-score raster: {novelty_path}")


def main() -> None:
    arguments = parse_arguments()
    analyses = (
        ["cosine", "euclidean", "knn"]
        if arguments.analysis == "all"
        else [arguments.analysis]
    )
    start_time = time.perf_counter()

    for index, change in enumerate(CHANGES, start=1):
        print(
            f"[{index}/{len(CHANGES)}] Comparing "
            f"{change['earlier']} to {change['later']}"
        )
        for analysis in analyses:
            print(f"\n=== Running {analysis} analysis ===")
            if analysis == "cosine":
                run_cosine(change)
            elif analysis == "euclidean":
                run_euclidean(change)
            else:
                run_knn(change)

    elapsed_seconds = time.perf_counter() - start_time
    print(f"Completed {len(CHANGES)} comparison(s) in {elapsed_seconds:.3f} seconds")


if __name__ == "__main__":
    main()