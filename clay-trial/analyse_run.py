import argparse
from analyse_cluster_viz import ClusterAnalyzer
from analyse_similarity_search import SimilarityAnalyzer
from analyse_umap_viz import UMAPAnalyzer
from analyse_visualize_pca import PCAAnalyzer


def main():
    parser = argparse.ArgumentParser(description="Run embedding analysis")
    parser.add_argument("--tile", required=True, help="Tile name (e.g., BA31_1000_4048.tiff)")
    parser.add_argument("--analysis", choices=["all", "cluster", "similarity", "umap", "pca"], 
                        default="all", help="Analysis to run")
    parser.add_argument("--n-clusters", type=int, default=20, help="Number of clusters for KMeans")
    parser.add_argument("--ref-row", type=int, help="Reference row for similarity")
    parser.add_argument("--ref-col", type=int, help="Reference col for similarity")
    
    args = parser.parse_args()
    
    ref_row_col = (args.ref_row, args.ref_col) if args.ref_row is not None and args.ref_col is not None else None
    
    if args.analysis in ["all", "cluster"]:
        print("\n=== Running Cluster Analysis ===")
        ClusterAnalyzer(args.tile, n_clusters=args.n_clusters).run()
    
    if args.analysis in ["all", "similarity"]:
        print("\n=== Running Similarity Analysis ===")
        SimilarityAnalyzer(args.tile, ref_row_col=ref_row_col).run()
    
    if args.analysis in ["all", "umap"]:
        print("\n=== Running UMAP Analysis ===")
        UMAPAnalyzer(args.tile).run()
    
    if args.analysis in ["all", "pca"]:
        print("\n=== Running PCA Analysis ===")
        PCAAnalyzer(args.tile).run()


if __name__ == "__main__":
    main()
