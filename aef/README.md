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

## Cosine Change Score

`locate_changes_cosine.py` compares the embedding at each pixel between the two
dates using cosine distance. Higher values indicate embeddings whose direction
has changed more; they are candidate changes, not a classified change type.

```powershell
.\.venv\Scripts\python.exe .\aef\locate_changes_cosine.py
```

Outputs:

- `cosine_change_score.tif`: continuous `float32` cosine-distance score. `0`
  means aligned embeddings; higher values mean greater dissimilarity; `NaN`
  denotes a pixel invalid in either source.
- `change_mask.tif`: binary `uint8` mask. `1` marks a score above the selected
  global percentile and `0` denotes all other pixels or invalid data.

The default `--percentile 95` selects approximately the highest 5% of valid
scores. The script also prints estimated score values at the 50th, 75th, 90th,
95th, and 99th percentiles. It reads data in 512-pixel windows, so it does not
load the full embedding rasters into memory.

Useful options:

```powershell
.\.venv\Scripts\python.exe .\aef\locate_changes_cosine.py --percentile 98 --block-size 1024
```

Use `--earlier`, `--later`, and `--output-directory` to override the default
paths.

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

Edit the `CHANGES` list in `run_locate_changes_cosine.py` to configure one or
more comparisons, then run:

```powershell
uv run python aef/run_locate_changes_cosine.py
```

Each list entry contains `earlier`, `later`, `output_directory`, `percentile`,
and `block_size`. Use a unique output directory for each comparison to avoid
overwriting `cosine_change_score.tif` and `change_mask.tif`.

## kNN Novelty Trial

`locate_changes_knn_novelty.py` is an experimental alternative. It randomly
samples 2019 embeddings as a reference distribution, then gives each sampled
2024 embedding the mean Euclidean distance to its `k` nearest reference
embeddings. Higher scores mean the 2024 embedding is less represented by the
sampled 2019 distribution.

```powershell
.\.venv\Scripts\python.exe .\aef\locate_changes_knn_novelty.py
```

It writes `knn_novelty_score.tif`. The default `--stride 16` creates a 160 m
output grid from 10 m inputs, `--reference-samples 10000` controls the size of
the 2019 sample, and `--neighbours 5` controls the average. These distances are
not bounded or directly comparable across runs with different settings; use them
to rank candidate locations within one run.