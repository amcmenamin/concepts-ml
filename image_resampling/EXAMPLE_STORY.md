# Wellington Image Alignment And Change Analysis

## Goal

Align two pairs of Wellington aerial images and resample all four images to a
common ground sample distance (GSD) of 0.3 metres. The resulting rasters can be
processed with the Clay geospatial foundation model to generate embeddings for
change detection and clustering etc.

## Scenario

One 2025 image at 0.075 m GSD covers the combined extent of two older images:

- A 2012-2013 image at 0.1 m GSD.
- A 2021 image at 0.075 m GSD.

Each older image is used as a reference grid. The 2025 image is clipped and
warped once to each reference raster's CRS, extent, pixel size, and grid origin.
This produces two spatially aligned image pairs.

## Input Files

Reference 1:

```text
C:\Data\clay\wellington\imagery\wellington\wellington_2012-2013_0.1m\rgb\2193\BQ32_500_021001.tiff
```

Reference 2:

```text
C:\Data\clay\wellington\imagery\wellington\wellington_2021_0.075m\rgb\2193\BQ32_500_021002.tiff
```

2025 input image:

```text
C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101.tiff
```

## Step 1: Download The Raw Images

The source images are public LINZ objects in the `nz-imagery` S3 bucket. The
following uses the same approach as
`run_resample_download.py`. Setting `raw=True`
copies the original raster bytes without resampling or recompression. An
available JSON file with the same basename is also copied.

```python
from pathlib import Path

from resample_aws_imagery import LinzRasterProcessor


OUTPUT_LOCATION = Path(r"C:\Data\clay\wellington\imagery")

INPUTS = [
  "s3://nz-imagery/wellington/wellington_2012-2013_0.1m/rgb/2193/BQ32_500_021001.tiff",
  "s3://nz-imagery/wellington/wellington_2021_0.075m/rgb/2193/BQ32_500_021002.tiff",
  "s3://nz-imagery/wellington/wellington_2025_0.075m/rgb/2193/BQ32_1000_1101.tiff",
]

for source in INPUTS:
  processor = LinzRasterProcessor(
    path=source,
    output_location=str(OUTPUT_LOCATION),
    raw=True,
  )
  processor.process()
```

The S3 paths are preserved beneath `OUTPUT_LOCATION`, producing the three local
input paths listed above.

The equivalent command-line form for one image is:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "s3://nz-imagery/wellington/wellington_2012-2013_0.1m/rgb/2193/BQ32_500_021001.tiff" `
  --raw `
  --output "C:\Data\clay\wellington\imagery"
```

## Step 2: Align The 2025 Image

Align the 2025 image to the 2012-2013 reference grid:

```powershell
uv run python image_resampling/align_rasters.py `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2012-2013_0.1m\rgb\2193\BQ32_500_021001.tiff" `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101.tiff" `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101_1.tiff"
```

Align the 2025 image to the 2021 reference grid:

```powershell
uv run python image_resampling/align_rasters.py `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2021_0.075m\rgb\2193\BQ32_500_021002.tiff" `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101.tiff" `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101_2.tiff"
```

The two outputs are:

```text
C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101_1.tiff
C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101_2.tiff
```

The aligned pairs are now:

1. `BQ32_500_021001.tiff` and `BQ32_1000_1101_1.tiff`.
2. `BQ32_500_021002.tiff` and `BQ32_1000_1101_2.tiff`.

## Step 3: Resample All Four Images To 0.3 Metres

Resample the 2012-2013 reference:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2012-2013_0.1m\rgb\2193\BQ32_500_021001.tiff" `
  --target-resolution 0.3 `
  --output "C:\Data\clay\wellington\imagery\wellington\wellington_2012-2013_0.1m\rgb\2193"
```

Resample its aligned 2025 image:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101_1.tiff" `
  --target-resolution 0.3 `
  --output "C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193"
```

Resample the 2021 reference:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2021_0.075m\rgb\2193\BQ32_500_021002.tiff" `
  --target-resolution 0.3 `
  --output "C:\Data\clay\wellington\imagery\wellington\wellington_2021_0.075m\rgb\2193"
```

Resample its aligned 2025 image:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193\BQ32_1000_1101_2.tiff" `
  --target-resolution 0.3 `
  --output "C:\Data\clay\wellington\imagery\wellington\wellington_2025_0.075m\rgb\2193"
```

The resampled filenames have the `_0.3m.tiff` suffix. Each pair now has the
same spatial coverage and a common 0.3 m GSD.

## Step 4: Generate And Analyse Embeddings

Run each 0.3 m raster through the Clay geospatial foundation model to generate
an embedding set. Because the images in each pair cover the same area on a
common grid, their embeddings can be compared spatially.

The embeddings can then support:

- Change detection between the older and 2025 imagery.
- Similarity searches for areas with comparable change patterns.
- Clustering to identify recurring land-cover or structural changes.
- Visual analysis of spatial and temporal embedding differences.
