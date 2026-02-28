import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from unittest.mock import patch

from app.data_download import CSV_DATASETS
from app.project_data import ProjectData, ProjectDataConfig


def _make_fake_world_gdf() -> gpd.GeoDataFrame:
	"""Return a tiny world-like GeoDataFrame used for fast tests."""
	return gpd.GeoDataFrame(
		{
			"ISO_A3": ["DEU", "BRA"],
			"NAME": ["Germany", "Brazil"],
			"CONTINENT": ["Europe", "South America"],
			"geometry": [Point(13, 52), Point(-47, -15)],
		},
		crs="EPSG:4326",
	)


def test_project_data_init_runs_pipeline_and_sets_attributes(tmp_path) -> None:
	"""ProjectData init should run both functions and expose loaded attributes."""
	fake_world = _make_fake_world_gdf()
	fake_raw_df = pd.DataFrame(
		{
			"Entity": ["Germany"],
			"Code": ["DEU"],
			"Year": [2020],
			"metric": [1.0],
		}
	)
	fake_merged = {name: fake_world.copy() for name in CSV_DATASETS}

	with (
		patch("app.project_data.download_datasets") as mock_download,
		patch("app.project_data.gpd.read_file", return_value=fake_world) as mock_read_map,
		patch("app.project_data.merge_datasets_with_map", return_value=fake_merged) as mock_merge,
		patch("app.project_data.pd.read_csv", return_value=fake_raw_df) as mock_read_csv,
	):
		config = ProjectDataConfig(downloads_dir=tmp_path)
		project_data = ProjectData(config=config)

	mock_download.assert_called_once_with(downloads_dir=str(tmp_path))
	mock_read_map.assert_called_once()
	mock_merge.assert_called_once()
	assert mock_read_csv.call_count == len(CSV_DATASETS)

	assert set(project_data.raw_datasets.keys()) == set(CSV_DATASETS.keys())
	assert set(project_data.merged_datasets.keys()) == set(CSV_DATASETS.keys())
	assert isinstance(project_data.world_map, gpd.GeoDataFrame)
	assert project_data.annual_change_forest_area.equals(fake_raw_df)