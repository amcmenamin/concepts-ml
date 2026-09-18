import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import geopandas as gpd
from shapely.geometry import Point

from export_capture_areas import CaptureAreaExporter


class CaptureAreaExporterTests(unittest.TestCase):
    def test_parse_collection_name(self) -> None:
        examples = {
            "upper-hutt_2017_0.1m": ("upper-hutt", "2017", 0.1),
            "wairarapa_sn11640_1989_0.75m": ("wairarapa", "1989", 0.75),
            "wellington_2012-2013_0.1m": ("wellington", "2012-2013", 0.1),
            "wellington_manawatu-whanganui_sn5139_1977_0.375m": (
                "wellington_manawatu-whanganui",
                "1977",
                0.375,
            ),
        }

        for collection, expected in examples.items():
            with self.subTest(collection=collection):
                self.assertEqual(
                    CaptureAreaExporter.parse_collection_name(collection), expected
                )

    @patch("export_capture_areas.get_public_store", return_value=object())
    @patch("export_capture_areas.obs.list")
    def test_export_downloads_only_exact_capture_area_names(
        self, list_objects: MagicMock, _get_store: MagicMock
    ) -> None:
        list_objects.return_value = [
            [
                {"path": "wellington/a/rgb/2193/capture-area.geojson"},
                {"path": "wellington/a/rgb/2193/collection.json"},
                {"path": "wellington/b/rgb/2193/capture-area.geojson"},
            ]
        ]
        exporter = CaptureAreaExporter(
            "s3://nz-imagery/wellington", r"C:\Data\capture-areas"
        )

        processor = MagicMock()
        with patch(
            "export_capture_areas.LinzRasterProcessor", return_value=processor
        ) as processor_class:
            exported = exporter.export()

        self.assertEqual(
            exported,
            [
                "s3://nz-imagery/wellington/a/rgb/2193/capture-area.geojson",
                "s3://nz-imagery/wellington/b/rgb/2193/capture-area.geojson",
            ],
        )
        list_objects.assert_called_once_with(
            exporter.source_store, prefix="wellington/"
        )
        self.assertEqual(processor_class.call_count, 2)
        self.assertEqual(processor.download_file.call_count, 2)

    @patch("export_capture_areas.get_public_store", return_value=object())
    def test_build_geoparquet_adds_folder_attributes(
        self, _get_store: MagicMock
    ) -> None:
        with TemporaryDirectory() as directory:
            output_root = Path(directory)
            first_path = (
                output_root
                / "wellington"
                / "hutt-city_2025_0.075m"
                / "rgb"
                / "2193"
                / "capture-area.geojson"
            )
            second_path = (
                output_root
                / "wellington"
                / "hutt-city_2025_0.075m"
                / "rgbnir"
                / "2193"
                / "capture-area.geojson"
            )
            for path, point in (
                (first_path, Point(174.9, -41.2)),
                (second_path, Point(175.0, -41.1)),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                gpd.GeoDataFrame(
                    {"geometry": [point]}, crs="EPSG:4326"
                ).to_file(path, driver="GeoJSON")

            exporter = CaptureAreaExporter(
                "s3://nz-imagery/wellington", str(output_root)
            )
            geoparquet_path, feature_count = exporter.build_geoparquet()
            result = gpd.read_parquet(geoparquet_path)

            self.assertEqual(feature_count, 2)
            self.assertEqual(result.crs.to_epsg(), 4326)
            self.assertEqual(
                set(result["collection"]), {"hutt-city_2025_0.075m"}
            )
            self.assertEqual(set(result["location"]), {"hutt-city"})
            self.assertEqual(set(result["basedate"]), {"2025"})
            self.assertEqual(set(result["GSD"]), {0.075})
            self.assertEqual(set(result["image_type"]), {"rgb", "rgbnir"})
            self.assertEqual(set(result["crs"]), {"2193"})
            self.assertEqual(
                set(result["s3_path"]),
                {
                    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/"
                    "rgb/2193/capture-area.geojson",
                    "s3://nz-imagery/wellington/hutt-city_2025_0.075m/"
                    "rgbnir/2193/capture-area.geojson",
                },
            )


if __name__ == "__main__":
    unittest.main()