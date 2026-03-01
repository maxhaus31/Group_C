import os
from typing import Dict, List

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point
from unittest.mock import patch

from app.data_download import merge_datasets_with_map, CSV_DATASETS


def _fake_world() -> gpd.GeoDataFrame:
    """Tiny world map with three countries."""
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
    """Write a minimal OWID-style CSV."""
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture()
def tmp_downloads(tmp_path: os.PathLike) -> str:
    """Fresh temporary directory to use as downloads_dir."""
    return str(tmp_path)


def _prepare_map_and_empty_zip(tmp_downloads: str, world: gpd.GeoDataFrame) -> None:
    """Create placeholder map ZIP and mock read_file."""
    open(os.path.join(tmp_downloads, "map_dataset.zip"), "wb").close()


def test_returns_dict_with_all_dataset_keys(tmp_downloads: str) -> None:
    """
    merge_datasets_with_map() must return one GeoDataFrame per CSV dataset.
    """
    world = _fake_world()
    _prepare_map_and_empty_zip(tmp_downloads, world)

    # Minimal valid CSV: one row per country, one year.
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
    Aggregate / invalid codes (non 3‑letter) must not affect merged data.
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
    All map countries must be present; countries with no data get NaN.
    """
    world = _fake_world()
    _prepare_map_and_empty_zip(tmp_downloads, world)

    # Only AAA and BBB have data.
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
