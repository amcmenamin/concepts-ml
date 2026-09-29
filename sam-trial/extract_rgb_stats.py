from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask

polygon_file = r"C:\Temp\imagery\class_test\processed\sam-labels\parquet\BQ32_500_030028_0.3m-64-8-9-1-100\BQ32_500_030028_0.3m-64-8-9-1-100.parquet"
rgb_image_file = r"C:\Data\clay\wellington\imagery\wellington\hutt-city_2025_0.075m\rgb\2193\BQ32_500_030028_0.3m.tiff"


def resolve_polygon_file(path: str | Path) -> Path:
	polygon_path = Path(path)
	if polygon_path.is_file():
		return polygon_path

	expected_file = polygon_path / f"{polygon_path.name}.parquet"
	if expected_file.is_file():
		return expected_file

	parquet_files = list(polygon_path.glob("*.parquet"))
	if len(parquet_files) != 1:
		raise ValueError(
			f"Expected one parquet file in {polygon_path}, found {len(parquet_files)}"
		)
	return parquet_files[0]


def calculate_rgb_means(
	polygons: gpd.GeoDataFrame, raster_path: str | Path
) -> gpd.GeoDataFrame:
	result = polygons.copy()

	with rasterio.open(raster_path) as source:
		if source.count < 3:
			raise ValueError("RGB raster must contain at least three bands")
		if source.crs is None or polygons.crs is None:
			raise ValueError("Both polygons and raster must have a CRS")

		raster_polygons = polygons.to_crs(source.crs)
		rgb_means: list[tuple[float, float, float]] = []

		for geometry in raster_polygons.geometry:
			if geometry is None or geometry.is_empty:
				rgb_means.append((np.nan, np.nan, np.nan))
				continue

			try:
				pixels, _ = mask(
					source,
					[geometry],
					indexes=[1, 2, 3],
					crop=True,
					all_touched=False,
					filled=False,
				)
			except ValueError:
				rgb_means.append((np.nan, np.nan, np.nan))
				continue

			rgb_means.append(
				tuple(
					float(band.mean()) if band.count() else np.nan
					for band in pixels
				)
			)

	result[["R_mean", "G_mean", "B_mean"]] = rgb_means
	return result


def main() -> None:
	source_path = resolve_polygon_file(polygon_file)
	polygons = gpd.read_parquet(source_path)
	result = calculate_rgb_means(polygons, rgb_image_file)
	output_path = source_path.with_name(f"{source_path.stem}_rgb_stats.parquet")
	result.to_parquet(output_path, index=False)
	print(f"Wrote RGB statistics for {len(result)} polygons: {output_path}")


if __name__ == "__main__":
	main()

