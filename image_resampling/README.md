# AWS Imagery Resampling

`resample_aws_imagery.py` reads public LINZ imagery from Amazon S3 or the local
filesystem. It can resample imagery to a configurable resolution (0.3 metres by
default) or copy the raw source bytes, then write the result to Amazon S3 or a
local directory. Resampled outputs preserve the input raster CRS; inputs without
a CRS remain unset and produce a warning in the log.

## Setup

From the repository root, install the project dependencies:

```powershell
uv sync
```

AWS credentials are not required to list or read the public `nz-imagery`
bucket. Writing to S3 requires credentials with access to the destination
bucket. Obstore uses the standard AWS credential chain, including environment
variables, shared AWS configuration files, and instance or task roles. Local
output does not require AWS credentials.

## Usage

```text
python image_resampling/resample_aws_imagery.py PATH [OPTIONS]
```

`PATH` may be either:

- A key relative to the default `nz-imagery` bucket.
- A complete `s3://bucket/key` URI.
- A public regional HTTPS URL in the form
  `https://s3.ap-southeast-2.amazonaws.com/bucket/key`.
- An absolute Windows or Linux local image path.
- A folder prefix when used with `--list-files` or `--all-imagery`.

## Options

| Option | Description |
| --- | --- |
| `-h`, `--help` | Display command help. |
| `--list-files` | List all objects beneath `PATH` without processing them. An output location is not required. |
| `--url-format {s3,http,both}` | Select the URL format printed by `--list-files`. The default is `s3`. |
| `--all-imagery` | Process every `.tiff` object beneath the folder specified by `PATH`. Without this option, `PATH` must identify one `.tiff` object. |
| `--raw` | Copy each source image without resampling or recompression. |
| `--download-file` | Copy one arbitrary file without TIFF validation or Rasterio processing. |
| `--target-resolution VALUE` | Output pixel resolution in the source CRS units. Defaults to `0.3`. Ignored with `--raw`. |
| `--source-bucket BUCKET` | Source bucket used for bucket-relative input paths. Defaults to `nz-imagery`. |
| `--aws-region REGION` | AWS region used for S3 stores and public HTTPS URLs. Defaults to `ap-southeast-2`. |
| `--output LOCATION` | Destination S3 bucket, `s3://` URI, or absolute local directory. Required unless `--list-files` is used. |
| `--log-file PATH` | Override the complete log file path. |
| `--default-log-file NAME` | Default log filename used when `--log-file` is omitted. Defaults to `resample_aws_imagery.log`. |

## Override Defaults

Processing defaults can be overridden without editing the script:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "wellington/carterton_2021_0.075m/rgb/2193/BP34_500_044060.tiff" `
  --output "C:\Data\clay\wellington\imagery" `
  --target-resolution 0.5 `
  --source-bucket nz-imagery `
  --aws-region ap-southeast-2 `
  --default-log-file aerial-resampling.log
```

## Logging And Timing

Every run prints and logs its start time, end time, elapsed processing time,
output location, and resolved log file path. Operational messages such as input
and written file paths are also logged. For local output, the log is appended to
`resample_aws_imagery.log` inside the output directory. S3 output and
listing-only runs use `resample_aws_imagery.log` in the current directory because
the log is written incrementally as a local file.

Set a different log path with `--log-file`:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "s3://nz-imagery/wellington/carterton_2021_0.075m/rgb/2193/BP34_500_044060.tiff" `
  --raw `
  --output "C:\Data\clay\wellington\imagery" `
  --log-file "C:\Data\clay\wellington\imagery\download.log"
```

With `--list-files`, object URLs remain on standard output so they can be
redirected to a text file. Status and timing messages go to standard error and
the log file.

## Download One File

Use `--download-file` to copy a single file such as `.json` or `.geojson`
without invoking Rasterio. The source-relative path is preserved beneath the
output location.

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "s3://nz-imagery/wellington/wellington_2017_0.1m/rgb/2193/capture-area.geojson" `
  --download-file `
  --output "C:\Data\clay\wellington\imagery"
```

Public HTTPS URLs work in the same mode:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "https://s3.ap-southeast-2.amazonaws.com/nz-imagery/wellington/wellington_2017_0.1m/rgb/2193/collection.json" `
  --download-file `
  --output "C:\Data\clay\wellington\imagery"
```

`--download-file` cannot be combined with `--list-files`, `--all-imagery`, or
`--raw`.

## List Files

List objects using the default S3 URL format:

```powershell
python image_resampling/resample_aws_imagery.py `
  "s3://nz-imagery/wellington/wellington_2017_0.1m" `
  --list-files
```

Print public HTTP URLs instead:

```powershell
python image_resampling/resample_aws_imagery.py `
  "s3://nz-imagery/wellington/wellington_2017_0.1m" `
  --list-files `
  --url-format http
```

Print both S3 and HTTP URLs for each object:

```powershell
python image_resampling/resample_aws_imagery.py `
  "wellington/wellington_2017_0.1m" `
  --list-files `
  --url-format both
```

The bucket-relative path in the final example uses `nz-imagery` automatically.
The verified Wellington prefix contains `.tiff`, `.json`, GeoJSON, and collection
metadata objects.

List the same folder using its public HTTPS path:

```powershell
python image_resampling/resample_aws_imagery.py `
  "https://s3.ap-southeast-2.amazonaws.com/nz-imagery/wellington/wellington_2017_0.1m" `
  --list-files `
  --url-format http
```

## S3 Output

Pass one `.tiff` key and a destination bucket. A bare bucket name is supported
for compatibility:

```powershell
python image_resampling/resample_aws_imagery.py `
  "s3://nz-imagery/wellington/wellington_2017_0.1m/rgb/2193/BP31_500_098091.tiff" `
  --output my-output-bucket
```

The output is written to:

```text
s3://my-output-bucket/wellington/wellington_2017_0.1m/rgb/2193/BP31_500_098091_0.3m.tiff
```

Use an S3 URI to write beneath a prefix in the bucket:

```powershell
python image_resampling/resample_aws_imagery.py `
  "wellington/wellington_2017_0.1m/rgb/2193/BP31_500_098091.tiff" `
  --output "s3://my-output-bucket/resampled"
```

The result is written beneath
`s3://my-output-bucket/resampled/wellington/wellington_2017_0.1m/rgb/2193/`.

The source image may also be supplied as a public HTTPS URL:

```powershell
python image_resampling/resample_aws_imagery.py `
  "https://s3.ap-southeast-2.amazonaws.com/nz-imagery/wellington/wellington_2017_0.1m/rgb/2193/BP31_500_098091.tiff" `
  --output my-output-bucket
```

## Local Output

Write to an absolute Windows directory:

```powershell
python image_resampling/resample_aws_imagery.py `
  "wellington/wellington_2017_0.1m/rgb/2193/BP31_500_098091.tiff" `
  --output "C:\data\resampled"
```

Write to an absolute Linux directory:

```bash
python image_resampling/resample_aws_imagery.py \
  "wellington/wellington_2017_0.1m/rgb/2193/BP31_500_098091.tiff" \
  --output "/data/resampled"
```

Both commands create
`wellington/wellington_2017_0.1m/rgb/2193/BP31_500_098091_0.3m.tiff` beneath the
specified directory.

## Target Resolution

The default output resolution is `0.3`. Override it with
`--target-resolution`; the value uses the source raster CRS units, typically
metres for LINZ imagery:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "s3://nz-imagery/wellington/carterton_2021_0.075m/rgb/2193/BP34_500_044060.tiff" `
  --target-resolution 0.5 `
  --output "C:\Data\clay\wellington\imagery"
```

This writes
`wellington/carterton_2021_0.075m/rgb/2193/BP34_500_044060_0.5m.tiff` beneath
the output directory. Resampled filenames always include the effective target
resolution. Raw copies keep the original filename.

## Download A Raw Image

Use `--raw` to download an S3 image without changing its pixels, metadata, or
compression. If a `.json` object with the same base name exists, it is copied
beside the image:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "s3://nz-imagery/wellington/carterton_2021_0.075m/rgb/2193/BP34_500_044060.tiff" `
  --raw `
  --output "C:\Data\clay\wellington\imagery"
```

The image and its available metadata are written to:

```text
C:\Data\clay\wellington\imagery\wellington\carterton_2021_0.075m\rgb\2193\BP34_500_044060.tiff
C:\Data\clay\wellington\imagery\wellington\carterton_2021_0.075m\rgb\2193\BP34_500_044060.json
```

## Local Input

Resample a local image into another local directory:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "C:\Data\imagery\source.tiff" `
  --output "C:\Data\imagery\resampled"
```

Copy a local image without resampling:

```powershell
uv run python image_resampling/resample_aws_imagery.py `
  "C:\Data\imagery\source.tiff" `
  --raw `
  --output "C:\Data\imagery\copies"
```

Raw local copies also include a same-basename `.json` file when one is present.

Absolute Linux input paths work in the same way:

```bash
uv run python image_resampling/resample_aws_imagery.py \
  "/data/imagery/source.tiff" \
  --output "/data/imagery/resampled"
```

## Align To A Reference Raster

`align_rasters.py` warps an input raster onto the exact pixel grid of a local
reference raster. The output copies the reference CRS, affine transform, width,
and height while retaining the input raster's bands and data type.

```powershell
uv run python image_resampling/align_rasters.py `
  "C:\Data\imagery\reference.tif" `
  "C:\Data\imagery\input.tif" `
  "C:\Data\imagery\aligned.tif" `
  --resampling bilinear
```

Available resampling methods are `nearest`, `bilinear`, and `cubic`. Use
`nearest` for categorical rasters. Both inputs must have a CRS, and neither
input is modified.

## Process A Folder

Use `--all-imagery` to recursively process every `.tiff` beneath a prefix:

```powershell
python image_resampling/resample_aws_imagery.py `
  "s3://nz-imagery/wellington/wellington_2017_0.1m/rgb/2193" `
  --all-imagery `
  --output my-output-bucket
```

This can process many large files. Use `--list-files` first to inspect the
selected prefix.

An absolute local folder can also be used with `--all-imagery`; `.tif` and
`.tiff` files are discovered recursively.

## Batch Process

`run_process.py` downloads the configured Wellington images in two phases: all
raw TIFF/JSON files first, followed by all resampled TIFFs.

```powershell
uv run python image_resampling/run_process.py
```

All files are written beneath `C:\Data\clay\wellington\imagery`, preserving
their paths relative to the `nz-imagery` bucket. This keeps imagery from
different years in separate collection directories.
