# AlphaEarth Change Detection

This folder compares co-registered Google AlphaEarth Foundation embedding
GeoTIFFs for the Wanaka area in 2019 and 2024. Both source files must have the
same band count, dimensions, coordinate reference system, and spatial transform.

The bundled defaults expect these inputs:

```text
C:\Data\AEF\wanaka\2019\xkmgcxnihpzce8az1-0000008192-0000000000.tiff
C:\Data\AEF\wanaka\2024\xd8jjxuf7h0qy40py-0000008192-0000000000.tiff
```

Results are written by default to `C:\Data\AEF\wanaka\change_detection`.

All three detectors require the earlier and later embedding GeoTIFFs to have
the same band count, dimensions, CRS, and affine transform. They produce
candidate change or novelty scores, not land-cover labels or a classification
of what changed. Invalid pixels are omitted from scoring and written as `NaN`
where applicable; cosine and kNN also exclude zero-length embedding vectors.

## Cosine Change Score

`locate_changes_cosine.py` compares the embedding at each pixel between the two
dates using cosine distance. Higher values indicate embeddings whose direction
has changed more; they are candidate changes, not a classified change type.

**Windows:**
```powershell
uv run python aef/locate_changes_cosine.py
```

**Linux/macOS:**
```bash
./.venv/bin/python ./aef/locate_changes_cosine.py
```

Outputs:

- `cosine_change_score.tif`: continuous `float32` cosine-distance score. `0`
  means aligned embedding directions; higher values mean greater directional
  dissimilarity, with a theoretical maximum of `2`.
- `change_mask.tif`: binary `uint8` mask. `1` marks a score above the selected
  global percentile and `0` denotes all other pixels or invalid data.

Use the score raster to rank the strength of directional change and the mask
to select the highest-scoring candidate locations. The mask is a statistical
threshold, not a confirmed change map.

The default `--percentile 95` selects approximately the highest 5% of valid
scores. The script also prints estimated score values at the 50th, 75th, 90th,
95th, and 99th percentiles. It reads data in 512-pixel windows, so it does not
load the full embedding rasters into memory.

Useful options:

**Windows:**
```powershell
uv run python aef/locate_changes_cosine.py --percentile 98 --block-size 1024
```

**Linux/macOS:**
```bash
./.venv/bin/python ./aef/locate_changes_cosine.py --percentile 98 --block-size 1024
```

Use `--earlier`, `--later`, and `--output-directory` to override the default
paths.

## Euclidean Change Score

`locate_changes_euclidean.py` measures the straight-line distance between the
earlier and later embedding vectors at each pixel. It detects changes in the
embedding vector's overall magnitude and position, whereas the cosine method
focuses on direction and ignores vector magnitude.

Run it directly with:

```powershell
uv run python aef/locate_changes_euclidean.py
```

It writes two GeoTIFFs:

- `euclidean_change_score.tif`: continuous `float32` Euclidean distance. A
  score of `0` means the two vectors are identical; larger values indicate a
  larger embedding difference. Scores depend on the scale of the embeddings,
  so they should not be compared directly with cosine scores.
- `euclidean_change_mask.tif`: binary `uint8` mask. `1` marks pixels above the
  selected percentile threshold; `0` marks lower-scoring or invalid pixels.

The default `--percentile 95` selects approximately the highest 5% of valid
Euclidean scores. Use `--earlier`, `--later`, `--output-directory`,
`--percentile`, and `--block-size` to override the defaults.

### Python API

Use `CosineChangeDetector` directly when change detection is part of another
Python workflow:

```python
from pathlib import Path

from locate_changes_cosine import CosineChangeDetector


detector = CosineChangeDetector(
  earlier_path=Path(r"C:\Data\AEF\wanaka\2019\earlier.tiff"),
  later_path=Path(r"C:\Data\AEF\wanaka\2024\later.tiff"),
  output_directory=Path(r"C:\Data\AEF\wanaka\change_detection\2019_to_2024"),
  percentile=95.0,
  block_size=512,
)
score_path, mask_path, threshold, score_percentiles = detector.run()
```

The constructor validates the percentile and block size. `run()` validates that
the rasters have matching bands and grids before writing the score and mask.

### Batch Runner

Edit the `CHANGES` list in `run_locate_changes.py` to configure one or
more comparisons, then run:

```bash
uv run python aef/run_locate_changes.py
```

This command works on both Windows and Linux/macOS.

The runner executes the cosine detector by default. Use `--analysis` to select
one detector or run all three:

```bash
uv run python aef/run_locate_changes.py --analysis all
```

The available values are `cosine`, `euclidean`, `knn`, and `all`.

Each list entry contains `earlier`, `later`, `output_directory`, `percentile`,
and `block_size`. Use a unique output directory for each comparison to avoid
overwriting the detector outputs.

The runner uses the same earlier/later pair for each selected detector. The
`knn` settings are currently fixed at stride `16`, `10,000` reference samples,
`5` neighbours, and seed `42`; its output is written as
`knn_novelty_score.tif` inside each comparison directory.

## kNN Novelty Trial

`locate_changes_knn_novelty.py` is an experimental alternative to direct
pixel-to-pixel change scores. It samples valid vectors from the earlier raster
as a reference distribution, then gives each valid later embedding the mean
Euclidean distance to its `k` nearest reference embeddings. Higher scores mean
the later embedding is less represented by the earlier sampled distribution.

**Windows:**
```powershell
uv run python aef/locate_changes_knn_novelty.py
```

**Linux/macOS:**
```bash
./.venv/bin/python ./aef/locate_changes_knn_novelty.py
```

It writes `knn_novelty_score.tif`, a single-band `float32` raster on a coarse
grid. The default `--stride 16` creates a 160 m output grid from 10 m inputs,
`--reference-samples 10000` controls the size of the earlier sample, and
`--neighbours 5` controls the average distance. These distances are not
bounded or directly comparable across runs with different settings; use them
to rank candidate locations within one run. This method does not write a
binary mask or perform exact full-resolution pixel-to-pixel comparison.