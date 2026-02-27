import os
import pandas as pd
import geopandas as gpd
import pytest
from unittest.mock import MagicMock, patch
from app.data_download import merge_datasets_with_map, DOWNLOADS_DIR, DATASETS, CSV_DATASETS
from shapely.geometry import Point


def _make_fake_csv(codes: list[str], years: list[int], value_col: str = "value") -> bytes:
    """Return a minimal OWID-style CSV as bytes."""
    rows = []
    for code, year in zip(codes, years):
        rows.append({"Entity": f"Country_{code}", "Code": code, "Year": year, value_col: 1.0})
    return pd.DataFrame(rows).to_csv(index=False).encode()


def _make_fake_world_gdf() -> gpd.GeoDataFrame:
    """Return a tiny GeoDataFrame that mimics the Natural Earth shapefile."""
    return gpd.GeoDataFrame(
        {
            "ISO_A3": ["DEU", "BRA", "USA"],
            "NAME": ["Germany", "Brazil", "United States"],
            "CONTINENT": ["Europe", "South America", "North America"],
            "geometry": [Point(13, 52), Point(-47, -15), Point(-98, 38)],
        },
        crs="EPSG:4326",
    )


def _write_fake_downloads(self, downloads_dir: str, fake_world: gpd.GeoDataFrame) -> None:
    """
    Write a fake map ZIP + one CSV per CSV_DATASETS entry into downloads_dir.
    The map is saved as a GeoPackage inside a zip so geopandas can read it,
    but for simplicity we patch gpd.read_file instead (see test fixtures).
    """
    # Write minimal CSV files
    for name in CSV_DATASETS:
        csv_bytes = _make_fake_csv(
            codes=["DEU", "BRA", "USA", "DEU", "BRA"],
            years=[2019, 2019, 2019, 2020, 2020],
            value_col="metric",
        )
        with open(os.path.join(downloads_dir, f"{name}.csv"), "wb") as fh:
            fh.write(csv_bytes)

    # Write a placeholder zip so the FileNotFoundError check passes
    open(os.path.join(downloads_dir, "map_dataset.zip"), "wb").close()

def test_returns_dict_with_all_dataset_keys(self, tmp_downloads: str) -> None:
    """merge_datasets_with_map() must return one GeoDataFrame per CSV dataset."""
    fake_world = _make_fake_world_gdf()
    self._write_fake_downloads(tmp_downloads, fake_world)

    with patch("app.data.gpd.read_file", return_value=fake_world):
        result = merge_datasets_with_map(downloads_dir=tmp_downloads)

    assert set(result.keys()) == set(CSV_DATASETS.keys())

def test_result_values_are_geodataframes(self, tmp_downloads: str) -> None:
    """Every value in the returned dict must be a GeoDataFrame (geometry preserved)."""
    fake_world = _make_fake_world_gdf()
    self._write_fake_downloads(tmp_downloads, fake_world)

    with patch("app.data.gpd.read_file", return_value=fake_world):
        result = merge_datasets_with_map(downloads_dir=tmp_downloads)

    for name, gdf in result.items():
        assert isinstance(gdf, gpd.GeoDataFrame), f"'{name}' is not a GeoDataFrame"
        assert "geometry" in gdf.columns, f"'{name}' is missing geometry column"

def test_uses_most_recent_year_only(self, tmp_downloads: str) -> None:
    """Only rows for the most recent year in each CSV must appear in the merged result."""
    fake_world = _make_fake_world_gdf()
    self._write_fake_downloads(tmp_downloads, fake_world)

    with patch("app.data.gpd.read_file", return_value=fake_world):
        result = merge_datasets_with_map(downloads_dir=tmp_downloads)

    # The fake CSVs have years 2019 and 2020; only 2020 rows should be merged.
    # Countries matched in 2020: DEU and BRA → metric is NOT NaN for them.
    # USA had no 2020 row → metric IS NaN.
    for name, gdf in result.items():
        if "metric" in gdf.columns:
            deu_row = gdf[gdf["ISO_A3"] == "DEU"]
            usa_row = gdf[gdf["ISO_A3"] == "USA"]
            assert not deu_row.empty and not deu_row["metric"].isna().all(), (
                f"DEU should have a value for the most recent year in '{name}'"
            )
            assert usa_row.empty or usa_row["metric"].isna().all(), (
                f"USA should have NaN (no 2020 row) in '{name}'"
            )

def test_row_count_equals_map_country_count(self, tmp_downloads: str) -> None:
    """
    The left join must preserve every row in the world map —
    no countries should be dropped even if they have no data.
    """
    fake_world = _make_fake_world_gdf()
    self._write_fake_downloads(tmp_downloads, fake_world)

    with patch("app.data.gpd.read_file", return_value=fake_world):
        result = merge_datasets_with_map(downloads_dir=tmp_downloads)

    expected_rows = len(fake_world)
    for name, gdf in result.items():
        assert len(gdf) == expected_rows, (
            f"'{name}' has {len(gdf)} rows but expected {expected_rows} "
            "(all world countries must be present)"
        )

def test_raises_if_map_file_missing(self, tmp_downloads: str) -> None:
    """FileNotFoundError must be raised when the map ZIP is absent."""
    with pytest.raises(FileNotFoundError, match="map_dataset.zip"):
        merge_datasets_with_map(downloads_dir=tmp_downloads)

def test_raises_if_csv_file_missing(self, tmp_downloads: str) -> None:
    """FileNotFoundError must be raised when a CSV dataset file is absent."""
    fake_world = _make_fake_world_gdf()
    # Write map placeholder but NO CSVs
    open(os.path.join(tmp_downloads, "map_dataset.zip"), "wb").close()

    with patch("app.data.gpd.read_file", return_value=fake_world):
        with pytest.raises(FileNotFoundError):
            merge_datasets_with_map(downloads_dir=tmp_downloads)

def test_raises_on_missing_code_column(self, tmp_downloads: str) -> None:
    """ValueError must be raised if a CSV is missing the 'Code' column."""
    fake_world = _make_fake_world_gdf()
    open(os.path.join(tmp_downloads, "map_dataset.zip"), "wb").close()

    # Write a bad CSV (no Code column) for the first dataset
    first_name = next(iter(CSV_DATASETS))
    bad_csv = pd.DataFrame({"Entity": ["Germany"], "Year": [2020], "metric": [1.0]})
    bad_csv.to_csv(os.path.join(tmp_downloads, f"{first_name}.csv"), index=False)

    with patch("app.data.gpd.read_file", return_value=fake_world):
        with pytest.raises(ValueError, match="Code"):
            merge_datasets_with_map(downloads_dir=tmp_downloads)


@pytest.fixture()
def tmp_downloads(tmp_path: os.PathLike) -> str:
    """Return a fresh temporary directory to use as downloads_dir."""
    return str(tmp_path)