"""
data_handler.py
---------------
Defines the OkavangoData class, which encapsulates downloading all required
environmental datasets and merging them with a world map GeoDataFrame.

All public methods and attributes are PEP 8-compliant.
Pydantic is used for configuration validation where applicable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from pydantic import BaseModel, field_validator


# Re-use the two core functions already written in data_download.py
from app.data_download import (
    CSV_DATASETS,
    DATASETS,
    DOWNLOADS_DIR,
    download_datasets,
    merge_datasets_with_map,
)


# Pydantic configuration model
class OkavangoConfig(BaseModel):
    """Validated configuration for the OkavangoData class."""

    downloads_dir: str = DOWNLOADS_DIR

    @field_validator("downloads_dir")
    @classmethod
    def must_be_non_empty_string(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("downloads_dir must not be an empty string.")
        return v


# Main class

class OkavangoData:
    """
    Central data handler for Project Okavango.

    On instantiation the class:
      1. Downloads all required datasets (skipping already-downloaded files).
      2. Merges each CSV dataset with the Natural Earth world map.
      3. Exposes the merged GeoDataFrames as instance attributes.

    Attributes
    ----------
    downloads_dir : str
        Directory where raw files are stored.
    merged : dict[str, gpd.GeoDataFrame]
        Mapping of dataset name → merged GeoDataFrame (world map + data).
    annual_change_forest_area : gpd.GeoDataFrame
        Annual change in forest area merged with world map.
    annual_deforestation : gpd.GeoDataFrame
        Annual deforestation merged with world map.
    share_land_protected : gpd.GeoDataFrame
        Share of land that is protected merged with world map.
    share_land_degraded : gpd.GeoDataFrame
        Share of land that is degraded merged with world map.
    forest_area_share : gpd.GeoDataFrame
        Forest area as a share of total land area merged with world map.
    """

    # Human-readable display labels for each dataset key
    DISPLAY_NAMES: dict[str, str] = {
        "annual_change_forest_area": "Annual Change in Forest Area",
        "annual_deforestation": "Annual Deforestation",
        "share_land_protected": "Share of Land Protected",
        "share_land_degraded": "Share of Land Degraded",
        "forest_area_share": "Forest Area (% of Land)",
    }

    # The single numeric column of interest in each dataset (auto-detected
    # at runtime, but we provide sensible fallbacks here for documentation).
    _VALUE_COLUMN_HINTS: dict[str, str] = {
        "annual_change_forest_area": "annual_change__in_forest_area",
        "annual_deforestation": "deforestation",
        "share_land_protected": "terrestrial_protected_areas__percent_of_total_land_area",
        "share_land_degraded": "proportion_of_land_that_is_degraded_over_total_land_area__percent",
        "forest_area_share": "forest_area__percent_of_land_area",
    }

    def __init__(self, downloads_dir: Optional[str] = None) -> None:
        """
        Initialise the OkavangoData handler.

        Parameters
        ----------
        downloads_dir : str, optional
            Override the default downloads directory.  Defaults to the
            ``DOWNLOADS_DIR`` constant defined in ``data_download.py``.
        """
        config = OkavangoConfig(
            downloads_dir=downloads_dir if downloads_dir is not None else DOWNLOADS_DIR
        )
        self.downloads_dir: str = config.downloads_dir

        # Step 1: download
        download_datasets(downloads_dir=self.downloads_dir)

        # Step 2: merge
        self.merged: dict[str, gpd.GeoDataFrame] = merge_datasets_with_map(
            downloads_dir=self.downloads_dir
        )

        # Step 3: expose individual GeoDataFrames as attributes
        self.annual_change_forest_area: gpd.GeoDataFrame = self.merged[
            "annual_change_forest_area"
        ]
        self.annual_deforestation: gpd.GeoDataFrame = self.merged["annual_deforestation"]
        self.share_land_protected: gpd.GeoDataFrame = self.merged["share_land_protected"]
        self.share_land_degraded: gpd.GeoDataFrame = self.merged["share_land_degraded"]
        self.forest_area_share: gpd.GeoDataFrame = self.merged["forest_area_share"]

    # Public helpers

    def get_value_column(self, dataset_key: str) -> str:
        """
        Return the name of the primary numeric column for a dataset.

        The column is detected automatically: after removing geographic
        metadata columns (ISO_A3, NAME, CONTINENT, geometry) the first
        remaining column is considered the value column.

        Parameters
        ----------
        dataset_key : str
            One of the keys in ``self.merged``.

        Returns
        -------
        str
            Column name.

        Raises
        ------
        KeyError
            If ``dataset_key`` is not found in ``self.merged``.
        ValueError
            If no numeric value column can be detected.
        """
        gdf = self.merged[dataset_key]
        meta_cols = {"ISO_A3", "NAME", "CONTINENT", "geometry"}
        value_cols = [c for c in gdf.columns if c not in meta_cols]
        if not value_cols:
            raise ValueError(
                f"No value column found for dataset '{dataset_key}'. "
                f"Columns present: {list(gdf.columns)}"
            )
        return value_cols[0]

    def top_bottom_countries(
        self,
        dataset_key: str,
        n: int = 5,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Return the top-n and bottom-n countries by the primary value column.

        Rows with NaN values are excluded.

        Parameters
        ----------
        dataset_key : str
            Key for one of the merged datasets.
        n : int
            Number of countries to include in each group (default 5).

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            ``(top_n, bottom_n)`` DataFrames, each containing ``NAME`` and
            the value column, sorted descending / ascending respectively.
        """
        gdf = self.merged[dataset_key]
        col = self.get_value_column(dataset_key)
        df = gdf[["NAME", col]].dropna(subset=[col]).copy()
        top = df.nlargest(n, col).reset_index(drop=True)
        bottom = df.nsmallest(n, col).reset_index(drop=True)
        return top, bottom
