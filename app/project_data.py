from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

# Get functions and constants from data_download.py.
from app.data_download import (
    CSV_DATASETS,
    DOWNLOADS_DIR,
    download_datasets,
    merge_datasets_with_map,
)


class ProjectDataConfig(BaseModel):
    """
    Configuration for ProjectData.

    Attributes:
        downloads_dir: Directory where downloaded and merged source files live.
    """

    # Make the config immutable. Prevent accidental changes to config values after initialization.
    model_config = ConfigDict(frozen=True)

    # Use default_factory to set default value for downloads_dir.
    downloads_dir: Path = Field(default_factory=lambda: Path(DOWNLOADS_DIR).resolve())


class ProjectData:
    """
    Central data access class for the project.

    During initialization this class:
    - Downloads all required datasets (Function 1).
    - Merges map geometry with all CSV datasets (Function 2).
    - Reads raw datasets into DataFrame attributes.

    The class keeps both dictionary-based access (for loops and dynamic usage)
    and explicit top-level attributes for commonly used data.
    """

    # Class attributes for configuration, paths, raw and merged datasets.
    config: ProjectDataConfig
    downloads_dir: Path
    world_map: gpd.GeoDataFrame
    raw_datasets: dict[str, pd.DataFrame]
    merged_datasets: dict[str, gpd.GeoDataFrame]

    annual_change_forest_area: pd.DataFrame
    annual_deforestation: pd.DataFrame
    share_land_protected: pd.DataFrame
    share_land_degraded: pd.DataFrame
    forest_area_share: pd.DataFrame

    def __init__(self, config: ProjectDataConfig | None = None) -> None:
        """
        Initialize project data and execute both base functions.

        Args:
            config: Optional validated pydantic configuration.
                    If not included, the default paths are used.
        """
        # Use provided config or default if None. 
        self.config = config or ProjectDataConfig()
        self.downloads_dir = self.config.downloads_dir

        # Download datasets to the specified directory. 
        download_datasets(downloads_dir=str(self.downloads_dir))

        # Load the world map and merge with CSV datasets. 
        self.world_map = gpd.read_file(self.downloads_dir / "map_dataset.zip")
        self.merged_datasets = merge_datasets_with_map(
            downloads_dir=str(self.downloads_dir),
            world_map=self.world_map,
        )
        self.raw_datasets = self._load_raw_csv_datasets()
        
        # Set explicit attributes for each dataset for convenient access.
        self.annual_change_forest_area = self.raw_datasets["annual_change_forest_area"]
        self.annual_deforestation = self.raw_datasets["annual_deforestation"]
        self.share_land_protected = self.raw_datasets["share_land_protected"]
        self.share_land_degraded = self.raw_datasets["share_land_degraded"]
        self.forest_area_share = self.raw_datasets["forest_area_share"]

    def _load_raw_csv_datasets(self) -> dict[str, pd.DataFrame]:
        """
        Read all raw CSV datasets from disk into memory.

        Returns:
            Dictionary mapping dataset key to raw pandas DataFrame.
        """
        datasets: dict[str, pd.DataFrame] = {}

        # Loop through CSV_DATASETS to read each CSV file into a DataFrame.
        for dataset_name in CSV_DATASETS:
            dataset_path = self.downloads_dir / f"{dataset_name}.csv"
            datasets[dataset_name] = pd.read_csv(dataset_path)

        return datasets
