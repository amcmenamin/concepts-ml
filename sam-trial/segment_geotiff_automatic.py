"""Generate automatic SAM instance masks for a GeoTIFF.

This uses Meta's original ``segment-anything`` package. Its checkpoint must
be a compatible SAM checkpoint, such as ``sam_vit_b_01ec64.pth``; an
Ultralytics SAM 2.1 checkpoint is not interchangeable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape
from segment_anything import SamAutomaticMaskGenerator, sam_model_registry


class SegmentGeotiffAutomatic:
    """Run Meta SAM automatic instance segmentation on GeoTIFF images."""

    def __init__(
        self,
        checkpoint: Path,
        model_type: str = "vit_b",
        device: str = "cpu",
        points_per_side: int = 32,
        pred_iou_thresh: float = 0.88,
        stability_score_thresh: float = 0.95,
        crop_n_layers: int = 1,
        min_mask_region_area: int = 100,
        append_parameters: bool = True,
    ) -> None:
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        self.append_parameters = append_parameters
        self.points_per_side = points_per_side
        self.pred_iou_thresh = pred_iou_thresh
        self.stability_score_thresh = stability_score_thresh
        self.crop_n_layers = crop_n_layers
        self.min_mask_region_area = min_mask_region_area
        sam = sam_model_registry[model_type](checkpoint=str(checkpoint))
        sam.to(device=device)
        self.mask_generator = SamAutomaticMaskGenerator(
            model=sam,
            points_per_side=points_per_side,
            pred_iou_thresh=pred_iou_thresh,
            stability_score_thresh=stability_score_thresh,
            crop_n_layers=crop_n_layers,
            min_mask_region_area=min_mask_region_area,
        )

    def output_path(self, output: Path) -> Path:
        """Return the output path, optionally including segmentation settings."""
        if not self.append_parameters:
            return output

        parameter_values = (
            str(self.points_per_side),
            format(self.pred_iou_thresh, "g").replace("0.", "").replace(".", ""),
            format(self.stability_score_thresh, "g").replace("0.", "").replace(".", ""),
            str(self.crop_n_layers),
            str(self.min_mask_region_area),
        )
        suffix = "-".join(parameter_values)
        return output.with_name(f"{output.stem}-{suffix}{output.suffix}")

    def write_vectors(
        self,
        masks: list[dict],
        transform: rasterio.Affine,
        crs: rasterio.crs.CRS | None,
        output_path: Path,
    ) -> Path:
        """Write mask polygons and shape metrics to a vector file."""
        if crs is None:
            raise ValueError("Input raster must have a CRS to create vector output")

        features = []
        for segment_id, mask in enumerate(masks, start=1):
            segmentation = mask["segmentation"].astype(np.uint8)
            for geometry, value in shapes(segmentation, transform=transform):
                if value:
                    features.append(
                        {
                            "geometry": shape(geometry),
                            "segment_id": segment_id,
                        }
                    )

        gdf = gpd.GeoDataFrame(features, crs=crs)
        if gdf.empty:
            gdf["area_m2"] = np.array([], dtype=float)
            gdf["perimeter_m"] = np.array([], dtype=float)
            gdf["compactness"] = np.array([], dtype=float)
            gdf["rectangularity"] = np.array([], dtype=float)
        else:
            gdf = gdf[gdf.geometry.area > 10].copy()
            gdf["geometry"] = gdf.geometry.simplify(0.3, preserve_topology=True)
            gdf["area_m2"] = gdf.geometry.area
            gdf["perimeter_m"] = gdf.geometry.length
            gdf["compactness"] = np.where(
                gdf["perimeter_m"] > 0,
                4 * np.pi * gdf["area_m2"] / gdf["perimeter_m"] ** 2,
                0,
            )
            rectangle_areas = gdf.geometry.apply(
                lambda geometry: geometry.minimum_rotated_rectangle.area
            )
            gdf["rectangularity"] = gdf["area_m2"] / rectangle_areas

        output_path = self.output_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() == ".gpkg":
            gdf.to_file(output_path, layer="contours", driver="GPKG")
        elif output_path.suffix.lower() == ".parquet":
            gdf.to_parquet(
                output_path,
                engine="pyarrow",
                compression="zstd",  
                write_covering_bbox=True,
                row_group_size=50000,
            )
        print(f"Wrote {len(gdf)} vector features: {output_path}")
        return output_path

    def segment(
        self,
        image_path: Path,
        output_path: Path,
        vector_output_path: Path | None = None,
    ) -> Path:
        """Segment one RGB GeoTIFF and return the path written."""
        if not image_path.is_file():
            raise FileNotFoundError(image_path)

        with rasterio.open(image_path) as source:
            bands = source.read()
            profile = source.profile.copy()
            transform = source.transform
            crs = source.crs

        if bands.shape[0] < 3:
            raise ValueError("SAM requires an image with at least three bands")
        image = np.moveaxis(bands[:3], 0, -1)
        image = np.clip(image, 0, 255).astype(np.uint8)

        masks = self.mask_generator.generate(image)
        if len(masks) > np.iinfo(np.uint16).max:
            raise ValueError("SAM returned more than 65,535 masks; reduce --points-per-side")

        masks.sort(key=lambda item: int(item["area"]), reverse=True)
        labelled = np.zeros(image.shape[:2], dtype=np.uint16)
        for mask_id, mask_data in enumerate(masks, start=1):
            labelled[mask_data["segmentation"]] = mask_id

        output = self.output_path(output_path)
        profile.update(driver="GTiff", count=1, dtype="uint16", nodata=0)
        output.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output, "w", **profile) as destination:
            destination.write(labelled, 1)

        print(f"Wrote {len(masks)} instance masks: {output}")
        if vector_output_path is not None:
            self.write_vectors(masks, transform, crs, vector_output_path)
        return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Input RGB GeoTIFF")
    parser.add_argument("output", type=Path, help="Output instance-label GeoTIFF")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--model-type",
        choices=("vit_h", "vit_l", "vit_b"),
        default="vit_b",
        help="SAM checkpoint architecture (default: vit_b)",
    )
    parser.add_argument("--device", default="cpu", help="Inference device (default: cpu)")
    parser.add_argument("--points-per-side", type=int, default=32)
    parser.add_argument("--pred-iou-thresh", type=float, default=0.88)
    parser.add_argument("--stability-score-thresh", type=float, default=0.95)
    parser.add_argument("--crop-n-layers", type=int, default=1)
    parser.add_argument(
        "--min-mask-region-area",
        type=int,
        default=100,
    )
    parser.add_argument(
        "--append-parameters",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Append SAM parameters to the output filename (default: enabled)",
    )
    parser.add_argument(
        "--vector-output",
        type=Path,
        help="Optional vector output (.gpkg, .geojson, or another GeoPandas-supported format)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    segmenter = SegmentGeotiffAutomatic(
        checkpoint=args.checkpoint,
        model_type=args.model_type,
        device=args.device,
        points_per_side=args.points_per_side,
        pred_iou_thresh=args.pred_iou_thresh,
        stability_score_thresh=args.stability_score_thresh,
        crop_n_layers=args.crop_n_layers,
        min_mask_region_area=args.min_mask_region_area,
        append_parameters=args.append_parameters,
    )
    segmenter.segment(args.image, args.output, args.vector_output)


if __name__ == "__main__":
    main()