# Clay Embedding Trial

This folder contains an exploratory workflow for generating and analysing geospatial embeddings with the Clay foundation model. It expects imagery and derived outputs under `data/`, configuration in `configs/metadata.yaml`, and a Clay checkpoint named `clay-v1.5.ckpt` available to the processing scripts.

https://clay-foundation.github.io/model/index.html

## Install

From the repository root, install dependencies with:

```powershell
uv sync
```

The project declares the Clay model package from its Git repository. Download or otherwise provide the model checkpoint separately before running processing.

## Workflow

1. Prepare imagery with `prep_imagery_nz.py` or the scripts under `sample_fire_clay/`.
2. Set the source tile and embedding mode in `process_model_nz_tiled.py`.
3. Run the processor from this directory so its relative paths resolve:

**Windows:**
```powershell
Set-Location .\clay-trial
uv run python process_model_nz_tiled.py
```

**Linux/macOS:**
```bash
cd ./clay-trial
uv run python process_model_nz_tiled.py
```

`EMBEDDING_MODE = "patches"` writes spatially detailed patch embeddings; `"cls"` writes one embedding per 256-pixel source tile. The output is a multi-band GeoTIFF, normally `data/<tile-name>/embeddings_tiled.tif`.

`process_highres.py` is a related processor for high-resolution imagery.

## Analysis

Use `run_analyse.py` to run one analysis or all of them against an embedding GeoTIFF:

**Windows:**
```powershell
uv run python clay-trial/run_analyse.py --path clay-trial/data/<tile-name>/embeddings_tiled.tif --analysis all
```

**Linux/macOS:**
```bash
uv run python clay-trial/run_analyse.py --path clay-trial/data/<tile-name>/embeddings_tiled.tif --analysis all
```

Supported analyses are:

- `cluster`: KMeans clustering through `analyse_cluster_viz.py`.
- `similarity`: embedding similarity search through `analyse_similarity_search.py`.
- `umap`: low-dimensional UMAP visualisation through `analyse_umap_viz.py`.
- `pca`: principal-component visualisation through `analyse_visualize_pca.py`.

For similarity search, supply `--ref-row` and `--ref-col` to choose a reference embedding location. `viz_example.py` provides feature-map visualisation for selected embedding dimensions.

## Visualizing embedding feature maps

`viz_example.py` reads a multi-band GeoTIFF and saves a grid of PNGs for each selected embedding dimension. Dimensions are zero-based, so dimension `0` is the first band in the file.

Example command from the repository root using the specific TIFF you provided:

**Windows:**
```powershell
uv run python clay-trial/viz_example.py "C:\Data\AEF\wanaka\2024\d8jjxuf7h0qy40py-0000008192-0000000000.tiff" --dimensions 0,1,2,3,4 --output-dir "C:\Data\AEF\wanaka\2024\viz"
```

**Linux/macOS:**
```bash
uv run python clay-trial/viz_example.py "/data/aef/wanaka/2024/d8jjxuf7h0qy40py-0000008192-0000000000.tiff" --dimensions 0,1,2,3,4 --output-dir "/data/aef/wanaka/2024/viz"
```

This plots the first five embedding bands into one or more PNG pages. If you want every Nth band instead of an explicit list, use `--step`:

**Windows:**
```powershell
uv run python clay-trial/viz_example.py "C:\Data\AEF\wanaka\2024\d8jjxuf7h0qy40py-0000008192-0000000000.tiff" --step 10 --output-dir "C:\Data\AEF\wanaka\2024\viz"
```

**Linux/macOS:**
```bash
uv run python clay-trial/viz_example.py "/data/aef/wanaka/2024/d8jjxuf7h0qy40py-0000008192-0000000000.tiff" --step 10 --output-dir "/data/aef/wanaka/2024/viz"
```

The script writes the PNGs beside the input TIFF by default, or to the directory passed via `--output-dir`.
