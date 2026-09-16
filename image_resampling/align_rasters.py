import argparse
from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


RESAMPLING_METHODS = {
    "nearest": Resampling.nearest,
    "bilinear": Resampling.bilinear,
    "cubic": Resampling.cubic,
}


class RasterAligner:
    def __init__(
        self,
        reference_path: str | Path,
        input_path: str | Path,
        output_path: str | Path,
        *,
        resampling: Resampling = Resampling.bilinear,
    ) -> None:
        self.reference_path = Path(reference_path).expanduser()
        self.input_path = Path(input_path).expanduser()
        self.output_path = Path(output_path).expanduser()
        self.resampling = resampling

    def align(self) -> Path:
        output_path = self.output_path.resolve()
        input_paths = (self.reference_path.resolve(), self.input_path.resolve())
        if output_path in input_paths:
            raise ValueError("Output path must differ from both input paths")

        with rasterio.open(self.reference_path) as reference:
            if reference.crs is None:
                raise ValueError("Reference raster must have a CRS")

            with rasterio.open(self.input_path) as source:
                if source.crs is None:
                    raise ValueError("Input raster must have a CRS")

                profile = source.profile.copy()
                profile.update(
                    driver="GTiff",
                    crs=reference.crs,
                    transform=reference.transform,
                    width=reference.width,
                    height=reference.height,
                    compress="deflate",
                )

                self.output_path.parent.mkdir(parents=True, exist_ok=True)
                with rasterio.open(self.output_path, "w", **profile) as destination:
                    for band_index in range(1, source.count + 1):
                        reproject(
                            source=rasterio.band(source, band_index),
                            destination=rasterio.band(destination, band_index),
                            src_transform=source.transform,
                            src_crs=source.crs,
                            src_nodata=source.nodata,
                            dst_transform=reference.transform,
                            dst_crs=reference.crs,
                            dst_nodata=source.nodata,
                            resampling=self.resampling,
                        )

        return self.output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Align an input raster to the exact grid of a reference raster"
    )
    parser.add_argument("reference", help="Raster that defines the output grid")
    parser.add_argument("input", help="Raster to align")
    parser.add_argument("output", help="Path for the aligned GeoTIFF")
    parser.add_argument(
        "--resampling",
        choices=tuple(RESAMPLING_METHODS),
        default="bilinear",
        help="Resampling algorithm (default: bilinear)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = RasterAligner(
        reference_path=args.reference,
        input_path=args.input,
        output_path=args.output,
        resampling=RESAMPLING_METHODS[args.resampling],
    ).align()
    print(output_path)


if __name__ == "__main__":
    main()