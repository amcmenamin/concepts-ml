import os
from pathlib import Path

# Prevent a system PostgreSQL installation from overriding Rasterio's bundled data.
os.environ.pop("GDAL_DATA", None)
os.environ.pop("PROJ_DATA", None)
os.environ.pop("PROJ_LIB", None)

import geopandas as gpd
import numpy as np
import pandas as pd
import pystac_client
import rasterio
import stackstac
from rasterio.enums import Resampling
from shapely import Point


class SentinelImageDownloader:
    """Download and cache Sentinel-2 imagery for a point and date range."""

    stac_api = "https://earth-search.aws.element84.com/v1"
    collection = "sentinel-2-l2a"
    assets = ["blue", "green", "red", "nir"]

    def __init__(
        self,
        latitude: float,
        longitude: float,
        start: str,
        end: str,
        output_path: Path,
        size: int = 256,
        gsd: int = 10,
    ) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.start = start
        self.end = end
        self.output_path = output_path
        self.size = size
        self.gsd = gsd

    def download(self) -> Path:
        if self.output_path.exists():
            print(f"Using cached image: {self.output_path}")
            return self.output_path

        items = self._find_items()
        epsg = int(items[0].properties["proj:code"].replace("EPSG:", ""))
        image_stack = stackstac.stack(
            items,
            bounds=self._bounds(epsg),
            snap_bounds=False,
            epsg=epsg,
            resolution=self.gsd,
            dtype="float64",
            rescale=False,
            fill_value=np.float64(0),
            assets=self.assets,
            resampling=Resampling.nearest,
        )

        print(image_stack)
        # This network cannot complete Windows certificate revocation checks.
        with rasterio.Env(GDAL_HTTP_UNSAFESSL="YES"):
            image_stack = image_stack.compute(scheduler="synchronous")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_geotiff(image_stack)
        print(f"Saved image: {self.output_path}")
        return self.output_path

    def _save_geotiff(self, image_stack) -> None:
        time_count, band_count, height, width = image_stack.shape
        profile = {
            "driver": "GTiff",
            "height": height,
            "width": width,
            "count": time_count * band_count,
            "dtype": image_stack.dtype,
            "crs": image_stack.attrs["crs"],
            "transform": image_stack.attrs["transform"],
            "compress": "deflate",
        }

        with rasterio.open(self.output_path, "w", **profile) as dataset:
            for time_index, timestamp in enumerate(image_stack.time.values):
                date = np.datetime_as_string(timestamp, unit="D")
                for band_index, band_name in enumerate(image_stack.band.values):
                    output_band = time_index * band_count + band_index + 1
                    dataset.write(image_stack.values[time_index, band_index], output_band)
                    dataset.set_band_description(output_band, f"{date}_{band_name}")

    def _find_items(self) -> list:
        catalog = pystac_client.Client.open(self.stac_api)
        search = catalog.search(
            collections=[self.collection],
            datetime=f"{self.start}/{self.end}",
            bbox=(
                self.longitude - 1e-5,
                self.latitude - 1e-5,
                self.longitude + 1e-5,
                self.latitude + 1e-5,
            ),
            max_items=100,
            query={"eo:cloud_cover": {"lt": 80}},
        )

        items = []
        dates = set()
        for item in search.item_collection():
            if item.datetime.date() not in dates:
                items.append(item)
                dates.add(item.datetime.date())

        if not items:
            raise RuntimeError("No Sentinel-2 scenes found for the requested point and dates.")

        print(f"Found {len(items)} items")
        return items

    def _bounds(self, epsg: int) -> tuple[float, float, float, float]:
        point = gpd.GeoDataFrame(
            pd.DataFrame(),
            crs="EPSG:4326",
            geometry=[Point(self.longitude, self.latitude)],
        ).to_crs(epsg)
        x, y = point.iloc[0].geometry.coords[0]
        half_width = self.size * self.gsd / 2
        return (x - half_width, y - half_width, x + half_width, y + half_width)


def main() -> None:
    downloader = SentinelImageDownloader(
        latitude=37.30939,
        longitude=-8.57207,
        start="2018-07-01",
        end="2018-09-01",
        output_path=Path("data/monchique_sentinel2.tif"),
    )
    downloader.download()


if __name__ == "__main__":
    main()
