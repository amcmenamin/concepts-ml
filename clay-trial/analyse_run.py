import argparse
from pathlib import Path

from analyse_cluster_viz import ClusterAnalyzer
from analyse_similarity_search import SimilarityAnalyzer
from analyse_umap_viz import UMAPAnalyzer
from analyse_visualize_pca import PCAAnalyzer


def main():
    parser = argparse.ArgumentParser(description="Run embedding analysis")
    parser.add_argument(
        "--path",
        required=True,
        type=Path,
        help="Path to the embeddings GeoTIFF (e.g., nz_embeddings_tiled.tif).",
    )
    parser.add_argument("--analysis", choices=["all", "cluster", "similarity", "umap", "pca"], 
                        default="all", help="Analysis to run")
    parser.add_argument("--n-clusters", type=int, default=20, help="Number of clusters for KMeans")
    parser.add_argument("--ref-row", type=int, help="Reference row for similarity")
    parser.add_argument("--ref-col", type=int, help="Reference col for similarity")
    
    args = parser.parse_args()

    if not args.path.is_file():
        parser.error(f"Embeddings file not found: {args.path}")

    ref_row_col = (args.ref_row, args.ref_col) if args.ref_row is not None and args.ref_col is not None else None
    
    if args.analysis in ["all", "cluster"]:
        print("\n=== Running Cluster Analysis ===")
        ClusterAnalyzer(args.path, n_clusters=args.n_clusters).run()
    
    if args.analysis in ["all", "similarity"]:
        print("\n=== Running Similarity Analysis ===")
        SimilarityAnalyzer(args.path, ref_row_col=ref_row_col).run()
    
    if args.analysis in ["all", "umap"]:
        print("\n=== Running UMAP Analysis ===")
        UMAPAnalyzer(args.path).run()
    
    if args.analysis in ["all", "pca"]:
        print("\n=== Running PCA Analysis ===")
        PCAAnalyzer(args.path).run()


if __name__ == "__main__":
    main()
