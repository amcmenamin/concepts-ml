import math
from pathlib import Path

import geopandas as gpd
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

#file = r"C:\Temp\imagery\class_test\processed\sam-labels\parquet\BQ32_500_030027_0.3m-64-8-9-1-100\BQ32_500_030027_0.3m-64-8-9-1-100.parquet"
file = r"C:\Temp\imagery\class_test\processed\sam-labels\parquet\BQ32_500_030028_0.3m-64-8-9-1-100\BQ32_500_030028_0.3m-64-8-9-1-100.parquet"
gdf = gpd.read_parquet(file)

minimum_bounding_rectangles = gdf.geometry.minimum_rotated_rectangle()
gdf["rectangularity_calculated"] = (
	gdf.geometry.area / minimum_bounding_rectangles.area
)
gdf["minimum_bounding_rectangle_fill"] = (
	gdf.geometry.area / minimum_bounding_rectangles.area
)
gdf["compactness_calculated"] = (
	4 * math.pi * gdf.geometry.area / gdf.geometry.length.pow(2)
)
gdf["boundary_complexity"] = gdf.geometry.length / gdf.geometry.area.pow(0.5)
gdf["convexity_calculated"] = gdf.geometry.area / gdf.geometry.convex_hull.area
gdf["vertex_count_calculated"] = gdf.geometry.exterior.apply(
	lambda exterior: len(exterior.coords) - 1
)


def oriented_aspect_ratio(rectangle):
	coordinates = list(rectangle.exterior.coords)[:4]
	side_lengths = [
		math.hypot(
			coordinates[(index + 1) % 4][0] - coordinates[index][0],
			coordinates[(index + 1) % 4][1] - coordinates[index][1],
		)
		for index in range(4)
	]
	return max(side_lengths) / min(side_lengths)


gdf["aspect_ratio_calculated"] = minimum_bounding_rectangles.apply(
	oriented_aspect_ratio
)


corner_angle_tolerance_degrees = 10


def corner_angle_counts(polygon):
	coordinates = list(polygon.exterior.coords)[:-1]
	near_90 = 0
	near_180 = 0

	for index, current in enumerate(coordinates):
		previous = coordinates[index - 1]
		next_coordinate = coordinates[(index + 1) % len(coordinates)]
		previous_vector = (
			previous[0] - current[0],
			previous[1] - current[1],
		)
		next_vector = (
			next_coordinate[0] - current[0],
			next_coordinate[1] - current[1],
		)
		previous_length = math.hypot(*previous_vector)
		next_length = math.hypot(*next_vector)
		if previous_length == 0 or next_length == 0:
			continue

		cosine = sum(
			previous_vector[coordinate] * next_vector[coordinate]
			for coordinate in range(2)
		) / (previous_length * next_length)
		angle = math.degrees(math.acos(max(-1, min(1, cosine))))
		near_90 += abs(angle - 90) <= corner_angle_tolerance_degrees
		near_180 += abs(angle - 180) <= corner_angle_tolerance_degrees

	return near_90, near_180


corner_angle_counts_by_polygon = gdf.geometry.apply(corner_angle_counts)
gdf["corner_count_near_90"] = [counts[0] for counts in corner_angle_counts_by_polygon]
gdf["corner_count_near_180"] = [counts[1] for counts in corner_angle_counts_by_polygon]

pca_metric_columns = [
	"area_m2",
	"rectangularity_calculated",
	"convexity_calculated",
	"aspect_ratio_calculated",
	"compactness_calculated",
	"boundary_complexity",
	"vertex_count_calculated",
	"corner_count_near_90",
	"corner_count_near_180",
]
scaled_metrics = StandardScaler().fit_transform(gdf[pca_metric_columns])
pca = PCA(n_components=2)
pca_coordinates = pca.fit_transform(scaled_metrics)
gdf["pca_1"] = pca_coordinates[:, 0]
gdf["pca_2"] = pca_coordinates[:, 1]

nearest_neighbors = NearestNeighbors(n_neighbors=2).fit(pca_coordinates)
neighbor_distances, neighbor_indices = nearest_neighbors.kneighbors(pca_coordinates)
gdf["nearest_similar_feature_index"] = neighbor_indices[:, 1]
gdf["nearest_similar_distance"] = neighbor_distances[:, 1]

source_path = Path(file)
full_output_path = source_path.with_name(f"{source_path.stem}_all_metrics.parquet")
filtered_output_path = source_path.with_name(
	f"{source_path.stem}_filtered.parquet"
)

gdf.to_parquet(full_output_path, index=False)

filtered_gdf = gdf[
	(gdf.geometry.area > 10)
	& (gdf.geometry.area < 1000)
	& (gdf["rectangularity_calculated"] > 0.70)
	& (gdf["convexity_calculated"] > 0.90)
	& (gdf["aspect_ratio_calculated"] < 5)
	& (gdf["compactness_calculated"] > 0.40)
].copy()
filtered_gdf.to_parquet(filtered_output_path, index=False)

print(f"Loaded {len(gdf)} features with CRS {gdf.crs}")
print(f"PCA explained variance ratio: {pca.explained_variance_ratio_}")
print(f"Exported full GeoDataFrame to {full_output_path}")
print(f"Exported {len(filtered_gdf)} filtered features to {filtered_output_path}")
print(
	gdf[
		[
			"segment_id",
			"compactness",
			"compactness_calculated",
			"boundary_complexity",
			"convexity_calculated",
			"vertex_count_calculated",
			"rectangularity",
			"rectangularity_calculated",
			"minimum_bounding_rectangle_fill",
			"aspect_ratio_calculated",
			"corner_count_near_90",
			"corner_count_near_180",
			"pca_1",
			"pca_2",
			"nearest_similar_feature_index",
			"nearest_similar_distance",
		]
	].head()
)

