import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
from rasterio.transform import from_origin

from align_rasters import RasterAligner


class RasterAlignerTests(unittest.TestCase):
    def test_align_uses_exact_reference_grid(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reference_path = root / "reference.tif"
            input_path = root / "input.tif"
            output_path = root / "aligned.tif"

            with rasterio.open(
                reference_path,
                "w",
                driver="GTiff",
                width=4,
                height=3,
                count=1,
                dtype="uint8",
                crs="EPSG:2193",
                transform=from_origin(100, 200, 10, 10),
            ) as reference:
                reference.write(np.ones((1, 3, 4), dtype="uint8"))

            with rasterio.open(
                input_path,
                "w",
                driver="GTiff",
                width=8,
                height=6,
                count=2,
                dtype="uint8",
                crs="EPSG:2193",
                transform=from_origin(95, 205, 5, 5),
            ) as source:
                source.write(np.ones((2, 6, 8), dtype="uint8"))

            RasterAligner(reference_path, input_path, output_path).align()

            with rasterio.open(reference_path) as reference:
                expected_grid = (
                    reference.crs,
                    reference.transform,
                    reference.width,
                    reference.height,
                )
            with rasterio.open(output_path) as output:
                actual_grid = (
                    output.crs,
                    output.transform,
                    output.width,
                    output.height,
                )
                self.assertEqual(actual_grid, expected_grid)
                self.assertEqual(output.count, 2)


if __name__ == "__main__":
    unittest.main()