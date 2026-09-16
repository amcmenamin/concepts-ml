# Studying Wellington Change With Clay Embeddings

## Research Goal

This study asks whether a geospatial foundation model can reveal meaningful
land-cover and structural differences between historical and recent Wellington
aerial imagery.

The [image alignment story](../image_resampling/EXAMPLE_STORY.md) prepares two
spatially matched image pairs:

1. 2012-2013 imagery and a 2025 image clipped to the same extent.
2. 2021 imagery and a 2025 image clipped to the same extent.

All four images are resampled to a common 0.3 metre ground sample distance
(GSD). This controls for pixel size and spatial coverage so that observed
embedding differences are less likely to be caused by grid misalignment.

## Prepared Images

The four inputs produced by the image-resampling workflow are:

```text
BQ32_500_021001_0.3m.tiff
BQ32_1000_1101_1_0.3m.tiff
BQ32_500_021002_0.3m.tiff
BQ32_1000_1101_2_0.3m.tiff
```

The comparison pairs are:

| Period | Historical image | Aligned 2025 image |
| --- | --- | --- |
| 2012-2013 to 2025 | `BQ32_500_021001_0.3m.tiff` | `BQ32_1000_1101_1_0.3m.tiff` |
| 2021 to 2025 | `BQ32_500_021002_0.3m.tiff` | `BQ32_1000_1101_2_0.3m.tiff` |

Copy or link these files into `clay-trial/data/`. Each filename must remain
unique because it determines the embedding output directory.

## Why Use A Geospatial Foundation Model?

A conventional pixel comparison is sensitive to illumination, colour balance,
season, shadows, and sensor differences. Clay transforms an image patch into a
high-dimensional representation learned from geospatial data. These embeddings
may preserve broader spatial and semantic properties such as vegetation,
buildings, roads, bare ground, and texture.

The experiment studies:

- Whether similar landscape types occupy similar regions of embedding space.
- Whether the same location has a stable representation across acquisition
  years.
- Where embedding patterns differ between the historical and 2025 images.
- Whether those differences correspond to plausible physical change rather
  than acquisition or preprocessing effects.

Embeddings are evidence for investigation, not proof that a real-world change
occurred. Candidate changes should be checked against the source imagery.

## Generate Clay Embeddings

[`process_model_nz_tiled.py`](process_model_nz_tiled.py) divides an image into
256 by 256 pixel tiles and sends each tile through the Clay v1.5 encoder. With
`EMBEDDING_MODE = "patches"`, the script retains the spatial patch tokens and
writes a georeferenced, 1024-band embedding GeoTIFF.

### Configure RGB Input

The prepared LINZ files are three-band RGB rasters. The current processor is
configured for four-band RGB+NIR imagery, so update its input configuration
before running this example:

```python
EMBEDDING_MODE = "patches"

platform = "linz"
band_names = ["red", "green", "blue"]
gsd = 0.3
```

The tile read must also use the three RGB bands:

```python
tile_data = src.read([1, 2, 3], window=window).astype(np.float32)
```

Do not label RGB imagery as `linz-nir` or synthesize an NIR band. The platform,
band order, normalization statistics, and wavelengths passed to Clay must match
the raster data.

### Process Each Image

Set `TILE_NAME` in `process_model_nz_tiled.py` to one prepared filename at a
time:

```python
TILE_NAME = "BQ32_500_021001_0.3m.tiff"
```

Run the processor from `clay-trial` so that its relative checkpoint, metadata,
and data paths resolve:

```powershell
Set-Location .\clay-trial
..\.venv\Scripts\python.exe .\process_model_nz_tiled.py
```

Repeat for all four filenames. The resulting embedding rasters are:

```text
data/BQ32_500_021001_0.3m/embeddings_tiled.tif
data/BQ32_1000_1101_1_0.3m/embeddings_tiled.tif
data/BQ32_500_021002_0.3m/embeddings_tiled.tif
data/BQ32_1000_1101_2_0.3m/embeddings_tiled.tif
```

The script processes only complete 256 by 256 tiles. Any partial tiles at the
right or bottom edge are omitted, so verify that paired embedding rasters still
have matching dimensions and transforms before comparing corresponding cells.

## Analyse Each Embedding Raster

Run all available exploratory analyses on each output. For example:

```powershell
..\.venv\Scripts\python.exe .\analyse_run.py `
  --path .\data\BQ32_500_021001_0.3m\embeddings_tiled.tif `
  --analysis all `
  --n-clusters 20
```

Repeat the command for the other three embedding paths. The generated products
are written beside each `embeddings_tiled.tif`.

## What The Analyses Study

### KMeans Clustering

[`analyse_cluster_viz.py`](analyse_cluster_viz.py) groups embedding cells into
recurring representation types and writes `clusters.tif` and `clusters.png`.
The map can reveal spatial units that Clay considers similar, such as coherent
vegetation, built surfaces, or other repeated textures.

Questions to inspect:

- Do clusters form coherent geographic regions rather than isolated noise?
- Do obvious roads, buildings, vegetation, and bare ground separate?
- Do areas that appear unchanged have similar cluster structure in both years?
- Do candidate change areas move into a different representation group?

Cluster IDs are arbitrary because KMeans is fitted independently for every
raster. Cluster 4 in one year is not automatically equivalent to cluster 4 in
another year. A direct temporal study should fit one clustering model to the
combined embeddings from both dates.

### Cosine Similarity Search

[`analyse_similarity_search.py`](analyse_similarity_search.py) averages the
embedding vectors in a 3 by 3 neighborhood around a selected cell and maps the
cosine similarity of every other cell to that reference. It writes
`similarity.tif` and `similarity.png`.

Choose the same `--ref-row` and `--ref-col` in both members of an aligned pair:

```powershell
..\.venv\Scripts\python.exe .\analyse_run.py `
  --path .\data\BQ32_500_021001_0.3m\embeddings_tiled.tif `
  --analysis similarity `
  --ref-row 100 `
  --ref-col 100
```

This tests whether an example landscape feature has the same spatial pattern of
similar locations in each year. The current analyzer performs similarity search
within one raster; it does not directly calculate historical-to-2025 embedding
distance.

### PCA Visualization

[`analyse_visualize_pca.py`](analyse_visualize_pca.py) reduces the 1024
embedding dimensions to three principal components and writes `pca_rgb.tif`
and `pca_rgb.png`. Broad colour regions show dominant axes of variation in the
embedding raster and are useful for spotting boundaries, gradients, and
outliers.

PCA is fitted independently to each raster. Its RGB colours and component axes
therefore cannot be compared directly between years. A shared PCA fitted to
both dates is required for consistent temporal colours.

### UMAP Visualization

[`analyse_umap_viz.py`](analyse_umap_viz.py) creates a nonlinear three-dimensional
projection and writes `umap_rgb.tif` and `umap_rgb.png`. It is useful for
exploring complex representation groupings that may not be visible with PCA.

UMAP colours are exploratory and independently scaled for each run. They are
not quantitative change scores, and matching colours across separate outputs
do not guarantee matching embeddings.

## Interpreting The Two Time Baselines

The 2012-2013 to 2025 pair provides a long change interval. It may expose major
urban development, vegetation succession, earthworks, or other persistent
land-cover transitions.

The 2021 to 2025 pair provides a shorter interval. It can help distinguish
recent changes from long-term trends and reveal whether apparent differences in
the longer comparison are stable in more recent imagery.

Compare each aligned pair using the same analysis settings and reference
locations. Look for agreement between:

- Visible changes in the RGB source images.
- Changes in embedding similarity patterns.
- Shifts in coherent cluster regions.
- Outliers or boundaries visible in PCA and UMAP products.

## Limits And Next Step

The current `analyse_*` scripts describe one embedding raster at a time. They do
not yet produce a direct change map between aligned dates. A quantitative next
step is to add a pairwise analyzer that reads two aligned embedding rasters and
calculates per-cell cosine distance or Euclidean distance. That map can then be
ranked, thresholded, clustered, and validated against the original imagery.

Other controls also matter. The current processor uses a fixed week and hour
for every image, so it does not encode the true acquisition date. Illumination,
season, source calibration, and resampling can still influence embeddings even
when geometry and GSD are matched.
