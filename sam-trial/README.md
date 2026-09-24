# SAM trial

Small experiments for running Segment Anything (SAM) against georeferenced
GeoTIFF imagery. The scripts read the first three raster bands as RGB, run
prompted or automatic segmentation, and write a one-band GeoTIFF while
preserving the source georeferencing and raster dimensions.

These scripts are experiments rather than a land-cover classification
pipeline. A point prompt tells SAM which object or region to segment; it does
not train a classifier or assign a semantic class automatically.

## Setup

From the repository root, install the project environment:

```powershell
uv sync
```

Run commands from the repository root with `uv run`, or activate the
corresponding virtual environment first. A PyTorch-compatible CPU or GPU
installation is required. Use `--device cuda` when the installed PyTorch
build and machine support CUDA.

## Checkpoints

The workflows use two different model APIs and checkpoint families:

| Script | API | Expected checkpoint |
| --- | --- | --- |
| `segment_geotiff.py` | Ultralytics | SAM 2.1 checkpoint, such as `sam2.1_s.pt` |
| `segment_landcover.py` | Ultralytics | SAM 2.1 checkpoint, such as `sam2.1_s.pt` |
| `segment_geotiff_automatic.py` | Meta `segment-anything` | Original SAM checkpoint, such as `sam_vit_b_01ec64.pth` |

An Ultralytics SAM 2.1 checkpoint cannot be passed to
`segment_geotiff_automatic.py`. Keep checkpoints outside source control; the
examples below assume they are stored in `sam-trial/.models/`.

## Input requirements

- The input must be a readable GeoTIFF with at least three bands.
- Only the first three bands are used.
- Values are clipped to `0..255` and converted to `uint8` before inference.
  Scale or prepare reflectance data beforehand if it is not already in that
  range.
- Prompt coordinates are pixel coordinates in `x,y` order, where `x` is the
  column and `y` is the row. They are not map coordinates.
- Output directories are created automatically.

## Workflows

### One point prompt

`segment_geotiff.py` creates a binary mask for one positive point prompt. The
output is a one-band `uint8` GeoTIFF: `0` is background and `1` is the mask.

```powershell
uv run python sam-trial/segment_geotiff.py `
  path\to\input.tiff `
  path\to\output-mask.tiff `
  --checkpoint sam-trial\.models\sam2.1_s.pt `
  --prompt-point 405,779 `
  --device cpu
```

From Windows Command Prompt, use `^` for line continuation:

```cmd
uv run python sam-trial\segment_geotiff.py ^
  path\to\input.tiff ^
  path\to\output-mask.tiff ^
  --checkpoint sam-trial\.models\sam2.1_s.pt ^
  --prompt-point 405,779 ^
  --device cpu
```

Options:

| Option | Default | Description |
| --- | --- | --- |
| `image` | required | Input GeoTIFF |
| `output` | required | Output binary mask GeoTIFF |
| `--checkpoint` | required | Ultralytics SAM checkpoint |
| `--prompt-point X,Y` | required | Positive pixel prompt |
| `--device` | `cpu` | PyTorch device, for example `cpu` or `cuda` |

### Multiple labelled prompts

`segment_landcover.py` runs one prompted segmentation per `--prompt` and
writes the results into one labelled raster. Each distinct class name receives
a sequential integer ID starting at `1`; `0` is background.

```powershell
uv run python sam-trial/segment_landcover.py `
  path\to\input.tiff `
  path\to\output-labels.tiff `
  --checkpoint sam-trial\.models\sam2.1_s.pt `
  --prompt vegetation,120,80 `
  --prompt building,350,220 `
  --device cpu
```

Windows Command Prompt:

```cmd
uv run python sam-trial\segment_landcover.py ^
  path\to\input.tiff ^
  path\to\output-labels.tiff ^
  --checkpoint sam-trial\.models\sam2.1_s.pt ^
  --prompt vegetation,120,80 ^
  --prompt building,350,220 ^
  --device cpu
```

Options:

| Option | Default | Description |
| --- | --- | --- |
| `image` | required | Input GeoTIFF |
| `output` | required | Output labelled GeoTIFF |
| `--checkpoint` | required | Ultralytics SAM checkpoint |
| `--prompt CLASS,X,Y` | required, repeatable | Class label and positive pixel prompt |
| `--device` | `cpu` | PyTorch device |

The output is `uint8`, so at most 255 distinct class IDs can be represented.
Later prompts overwrite earlier labels where their masks overlap. The script
prints the class-to-ID mapping after processing.

### Automatic instance masks

`segment_geotiff_automatic.py` uses Meta's original SAM automatic mask
 generator. It does not need point prompts and writes each generated instance
as a `uint16` label. `0` is background and instance IDs start at `1`.

```powershell
uv run python sam-trial/segment_geotiff_automatic.py `
  path\to\input-rgb.tiff `
  path\to\automatic-labels.tiff `
  --checkpoint sam-trial\.models\sam_vit_b_01ec64.pth `
  --model-type vit_b `
  --points-per-side 32 `
  --pred-iou-thresh 0.88 `
  --stability-score-thresh 0.95 `
  --crop-n-layers 1 `
  --min-mask-region-area 100 `
  --device cpu
```

Windows Command Prompt:

```cmd
uv run python sam-trial\segment_geotiff_automatic.py ^
  path\to\input-rgb.tiff ^
  path\to\automatic-labels.tiff ^
  --checkpoint sam-trial\.models\sam_vit_b_01ec64.pth ^
  --model-type vit_b ^
  --points-per-side 32 ^
  --pred-iou-thresh 0.88 ^
  --stability-score-thresh 0.95 ^
  --crop-n-layers 1 ^
  --min-mask-region-area 100 ^
  --append-parameters ^
  --device cpu
```

Output parameter suffixes are enabled by default. The five values are appended
in this order:
`points-per-side`, `pred-iou-thresh`, `stability-score-thresh`,
`crop-n-layers`, and `min-mask-region-area`. For example,
`automatic-labels.tiff` becomes `automatic-labels-32-88-95-1-100.tiff` with
the defaults above. Use `--no-append-parameters` to keep the output name
unchanged.

Options:

| Option | Default | Description |
| --- | --- | --- |
| `image` | required | Input RGB GeoTIFF |
| `output` | required | Output instance-label GeoTIFF |
| `--checkpoint` | required | Original Meta SAM checkpoint |
| `--model-type` | `vit_b` | Checkpoint architecture: `vit_b`, `vit_l`, or `vit_h` |
| `--device` | `cpu` | PyTorch device |
| `--points-per-side` | `32` | Automatic mask sampling density; higher values cost more memory and time |
| `--pred-iou-thresh` | `0.88` | Predicted mask quality threshold; higher values keep fewer, more selective masks |
| `--stability-score-thresh` | `0.95` | Mask stability threshold; higher values keep fewer, more stable masks |
| `--crop-n-layers` | `1` | Number of image-crop layers used for multi-scale mask generation |
| `--min-mask-region-area` | `100` | Removes small disconnected mask regions below this pixel area |
| `--append-parameters` / `--no-append-parameters` | on | Enable or disable appending all five automatic-mask settings to the output filename |
| `--vector-output` | off | Also write mask polygons and shape metrics to a GeoPackage, Parquet supported formats |

Use `--vector-output` to write polygons as well as the labelled raster. Each
connected mask region becomes a feature. Regions with area `<= 10` are
removed, and geometries are simplified with a tolerance of `0.3` before these
metrics are written:

- `area_m2`: polygon area
- `perimeter_m`: polygon perimeter
- `compactness`: $4\pi\times area\,/\,perimeter^2$
- `rectangularity`: polygon area divided by its minimum rotated rectangle area

The input raster must have a CRS. The metric names assume a projected CRS
whose units are metres, such as EPSG:2193.

The reusable `SegmentGeotiffAutomatic` class in
`segment_geotiff_automatic.py` provides the same processing API for Python
callers. The `run_segment_geotiff_auto.py` runner loads the SAM model once and
supports either one input image or a folder of images.

For one image:

```powershell
uv run python sam-trial/run_segment_geotiff_auto.py `
  path\to\input-rgb.tiff `
  path\to\automatic-labels.tiff `
  --checkpoint sam-trial\.models\sam_vit_b_01ec64.pth `
  --crop-n-layers 1 `
  --min-mask-region-area 100 `
  --append-parameters `
  --vector-output path\to\automatic-labels.gpkg `
  --device cpu
```

For a folder, the runner processes `.tif` and `.tiff` files in that folder
and writes matching output names to the output folder:

```cmd
uv run python sam-trial\run_segment_geotiff_auto.py ^
  C:\Data\imagery\input ^
  C:\Temp\imagery\labels ^
  --checkpoint sam-trial\.models\sam_vit_b_01ec64.pth ^
  --points-per-side 32 ^
  --pred-iou-thresh 0.88 ^
  --stability-score-thresh 0.95 ^
  --crop-n-layers 1 ^
  --min-mask-region-area 100 ^
  --append-parameters ^
  --vector-output C:\Temp\imagery\vectors ^
  --device cpu
```

When processing a folder, `--vector-output` is treated as a folder. One
GeoPackage is written per input image, using the input stem as its base name.

These settings trade coverage, detail, runtime, and output size. They are
starting points rather than guaranteed quality levels; test them on a
representative crop before processing a large raster.

| Use case | `--points-per-side` | `--pred-iou-thresh` | `--stability-score-thresh` | Likely impact |
| --- | ---: | ---: | ---: | --- |
| Fast exploratory run | `16` | `0.80` | `0.90` | Lower memory use and faster processing; fewer small or difficult objects may be found, with more permissive masks. |
| General starting point | `32` | `0.88` | `0.95` | Balanced sampling and filtering; the recommended baseline for comparing runs. |
| More detailed run | `64` | `0.88` | `0.95` | Denser sampling can find smaller or narrowly placed objects, but increases runtime and memory substantially. |
| Conservative, high-confidence output | `32` | `0.92` | `0.97` | Fewer masks and less unstable output; recall may drop for low-contrast, thin, or irregular objects. |
| Maximum small-object search | `64` | `0.80` | `0.90` | Highest candidate coverage of these examples, but potentially many overlapping/noisy masks and the greatest runtime, memory, and output-label pressure. |

If processing fails with an out-of-memory error, first reduce
`--points-per-side`; if the output contains too many noisy masks, increase
the two threshold values or reduce the sampling density.

The automatic workflow limits the output to 65,535 instances because labels
are stored as `uint16`. If that limit is exceeded, reduce
`--points-per-side`.

## Convenience runner

`run_segment_geotiff.py` is a local convenience wrapper for the one-point
workflow. Edit its `IMAGE`, `OUTPUT`, `CHECKPOINT`, `PROMPT_POINT`, and
`DEVICE` constants before running:

```powershell
uv run python sam-trial/run_segment_geotiff.py
```

The file currently contains several historical assignments to
`PROMPT_POINT`; Python uses the last assignment. Remove the unused assignments
when adapting the example so the selected point is obvious.

## Limitations and review notes

- Inputs with more than three bands are silently reduced to the first three;
  band order and value scaling must therefore be checked by the caller.
- Prompted segmentation is sequential. Overlapping masks are resolved by the
  last prompt, not by confidence or area.
- The output preserves the source profile but does not add a class or instance
  color table.
- The scripts load the complete raster into memory, so large GeoTIFFs may need
  tiling or windowed processing before use.
- Pixel prompts must be supplied manually; there is no coordinate transform or
  map-coordinate interface.

Inspect the command-line help for the exact parser interface:

```powershell
uv run python sam-trial/segment_geotiff.py --help
uv run python sam-trial/segment_landcover.py --help
uv run python sam-trial/segment_geotiff_automatic.py --help
```
