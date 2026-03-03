import os
from typing import Dict, List

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point
from unittest.mock import patch

from app.data_download import merge_datasets_with_map, CSV_DATASETS


def _fake_world() -> gpd.GeoDataFrame:
    """
    Create a minimal fake world map for testing merge logic.

    Returns 3 fake countries (AAA, BBB, CCC) that mimic the Natural Earth
    shapefile structure. Used by all tests to provide consistent world data.

    Returns:
        GeoDataFrame with ISO_A3, NAME, CONTINENT, geometry columns
    """
    return gpd.GeoDataFrame(
        {
            "ISO_A3": ["AAA", "BBB", "CCC"],
            "NAME": ["Country_AAA", "Country_BBB", "Country_CCC"],
            "CONTINENT": ["Europe", "Asia", "Africa"],
            "geometry": [Point(0, 0), Point(1, 1), Point(2, 2)],
        },
        crs="EPSG:4326",
    )


def _write_csv(
    path: str,
    rows: List[Dict],
) -> None:
    """
    Write test CSV data in Our World in Data format.

    Creates minimal CSV files with Entity/Code/Year/metric columns that
    merge_datasets_with_map requires.
    """
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture()
def tmp_downloads(tmp_path: os.PathLike) -> str:
    """Provide fresh temporary downloads directory for each test."""
    return str(tmp_path)


def _prepare_map_and_empty_zip(tmp_downloads: str, world: gpd.GeoDataFrame) -> None:
    """
    Create empty map ZIP file so file existence checks pass.
    Mocks gpd read_file separately to return test data.
    """
    open(os.path.join(tmp_downloads, "map_dataset.zip"), "wb").close()


def test_returns_dict_with_all_dataset_keys(tmp_downloads: str) -> None:
    """
    Test merge_datasets_with_map() returns dict with one GeoDataFrame per dataset.

    1. Result is dict with all CSV_DATASETS keys
    2. Each value is GeoDataFrame with geometry column preserved
    """
    world = _fake_world()
    _prepare_map_and_empty_zip(tmp_downloads, world)

    base_rows = [
        {"Entity": "Country_AAA", "Code": "AAA", "Year": 2020, "metric": 1.0},
        {"Entity": "Country_BBB", "Code": "BBB", "Year": 2020, "metric": 2.0},
        {"Entity": "Country_CCC", "Code": "CCC", "Year": 2020, "metric": 3.0},
    ]

    for name in CSV_DATASETS:
        csv_path = os.path.join(tmp_downloads, f"{name}.csv")
        _write_csv(csv_path, base_rows)

    with patch("app.data_download.gpd.read_file", return_value=world):
        result = merge_datasets_with_map(downloads_dir=tmp_downloads)

    assert isinstance(result, dict)
    assert set(result.keys()) == set(CSV_DATASETS.keys())
    for gdf in result.values():
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert "geometry" in gdf.columns


def test_filters_out_aggregate_and_invalid_codes(tmp_downloads: str) -> None:
    """
    Test merge_datasets_with_map() ignores aggregate rows and invalid country codes.

    Verifies regex filter ^[A-Z]{3}$ excludes:
    1. Empty Code: ""
    2. 4+ letters: EU27
    3. 2 letters: AB

    Only exact 3-letter ISO codes get merged.
    """
    world = _fake_world()
    _prepare_map_and_empty_zip(tmp_downloads, world)

    valid_rows = [
        {"Entity": "Country_AAA", "Code": "AAA", "Year": 2020, "metric": 1.0},
        {"Entity": "Country_BBB", "Code": "BBB", "Year": 2020, "metric": 2.0},
    ]
    aggregate_rows = [
        {"Entity": "World", "Code": "", "Year": 2020, "metric": 999.0},
        {"Entity": "Europe", "Code": "EU27", "Year": 2020, "metric": 888.0},
        {"Entity": "Invalid", "Code": "AB", "Year": 2020, "metric": 777.0},
    ]
    all_rows = valid_rows + aggregate_rows

    for name in CSV_DATASETS:
        csv_path = os.path.join(tmp_downloads, f"{name}.csv")
        _write_csv(csv_path, all_rows)

    with patch("app.data_download.gpd.read_file", return_value=world):
        result = merge_datasets_with_map(downloads_dir=tmp_downloads)

    for gdf in result.values():
        aaa = gdf[gdf["ISO_A3"] == "AAA"]["metric"]
        bbb = gdf[gdf["ISO_A3"] == "BBB"]["metric"]
        ccc = gdf[gdf["ISO_A3"] == "CCC"]["metric"]

        assert aaa.iloc[0] == 1.0
        assert bbb.iloc[0] == 2.0
        # CCC has no valid CSV row → NaN
        assert ccc.isna().all()


def test_left_join_preserves_all_map_countries(tmp_downloads: str) -> None:
    """
    Test left join keeps all world map countries, even without CSV data.

    1. Row count matches world map exactly
    2. Countries with CSV data get values
    3. Countries without CSV data get NaN
    """
    world = _fake_world()
    _prepare_map_and_empty_zip(tmp_downloads, world)

    rows = [
        {"Entity": "Country_AAA", "Code": "AAA", "Year": 2020, "metric": 5.0},
        {"Entity": "Country_BBB", "Code": "BBB", "Year": 2020, "metric": 6.0},
    ]

    for name in CSV_DATASETS:
        csv_path = os.path.join(tmp_downloads, f"{name}.csv")
        _write_csv(csv_path, rows)

    with patch("app.data_download.gpd.read_file", return_value=world):
        result = merge_datasets_with_map(downloads_dir=tmp_downloads)

    expected_rows = len(world)

    for gdf in result.values():
        # All countries preserved
        assert len(gdf) == expected_rows

        aaa = gdf[gdf["ISO_A3"] == "AAA"]["metric"]
        bbb = gdf[gdf["ISO_A3"] == "BBB"]["metric"]
        ccc = gdf[gdf["ISO_A3"] == "CCC"]["metric"]

        assert not aaa.isna().all()
        assert not bbb.isna().all()
        assert ccc.isna().all()
