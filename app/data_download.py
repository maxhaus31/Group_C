import os
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "downloads")

# URLs for all datasets (map + CSVs).
DATASETS = {
    "annual_change_forest_area": "https://ourworldindata.org/grapher/annual-change-forest-area.csv?v=1&csvType=full&useColumnShortNames=true",
    "annual_deforestation": "https://ourworldindata.org/grapher/annual-deforestation.csv?v=1&csvType=full&useColumnShortNames=true",
    "share_land_protected": "https://ourworldindata.org/grapher/terrestrial-protected-areas.csv?v=1&csvType=full&useColumnShortNames=true",
    "share_land_degraded": "https://ourworldindata.org/grapher/share-degraded-land.csv?v=1&csvType=full&useColumnShortNames=true",
    "forest_area_share": "https://ourworldindata.org/grapher/forest-area-as-share-of-land-area.csv?v=1&csvType=full&useColumnShortNames=true",
    "map_dataset": "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip",
}

# CSV datasets only (excludes the map shapefile)
CSV_DATASETS = {k: v for k, v in DATASETS.items() if not v.endswith(".zip")}


def download_datasets(downloads_dir: str = DOWNLOADS_DIR) -> None:
    """
    Downloads all required datasets into the downloads directory.

    Skips files that have already been downloaded. The map dataset is a ZIP
    file and will be loaded with geopandas directly: world = gpd.read_file("downloads/map_dataset.zip")

    Args:
        downloads_dir: Path to the directory where files will be saved.
                       Defaults to the standard DOWNLOADS_DIR constant.
    """

    os.makedirs(downloads_dir, exist_ok=True)

    # Download each dataset if not already present
    for name, url in DATASETS.items():
        extension = ".zip" if url.endswith(".zip") else ".csv"
        file_path = os.path.join(downloads_dir, f"{name}{extension}")

        # Skip download if file already exists
        if os.path.exists(file_path):
            print(f"[SKIP] {name} already downloaded.")
            continue

        print(f"[DOWNLOADING] {name}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Save the file to disk
        with open(file_path, "wb") as f:
            f.write(response.content)

        # Validate that the file is saved
        print(f"[OK] {name} saved to {file_path}")


<<<<<<< Updated upstream
def merge_datasets_with_map(
    downloads_dir: str = DOWNLOADS_DIR,
    world_map: Optional[gpd.GeoDataFrame] = None,
) -> dict[str, gpd.GeoDataFrame]:
    """
    Merges the Natural Earth world map with each CSV dataset.

    For each dataset, only the most recent year of data is used (determined
    dynamically — never hardcoded). The merge is performed on ISO 3-letter
    country codes (ISO_A3 in the shapefile, Code in the OWID CSVs), with the
    GeoDataFrame always on the left so that geometry is preserved.
=======

def merge_datasets_with_map(downloads_dir: str = DOWNLOADS_DIR, 
                            world_map: gpd.GeoDataFrame | None = None,) -> dict[str, gpd.GeoDataFrame]:
    """
    Merges the Natural Earth world map with each CSV dataset.

    For each dataset, only the most recent year of data is used, which is determined dynamically. 
    The merge is performed using ISO 3-letter country codes. 
    The GeoDataFrame is always on the left to ensure that geometry.

    Args:
        downloads_dir: Path to the directory containing the downloaded files.
                       Defaults to DOWNLOADS_DIR.
        world_map: Optional preloaded world map GeoDataFrame. If provided,
                   the function reuses it instead of reading map_dataset.zip.

    Returns:
        A dictionary mapping each dataset name (str) to a merged GeoDataFrame.
        Each GeoDataFrame contains all world countries, with the dataset columns
        joined where a match exists (NaN where no match is found).

    Raises:
        FileNotFoundError: If the map shapefile or a CSV file is not found.
                           Run download_datasets() first.
        ValueError: If a CSV is missing the expected 'Code' or 'Year' columns.
>>>>>>> Stashed changes
    """

    # Check if the map is already provided. Raise an error if missing and not provided.
    if world_map is None:
        map_path = os.path.join(downloads_dir, "map_dataset.zip")

        if not os.path.exists(map_path):
            raise FileNotFoundError(
                f"Map file not found at '{map_path}'. Please run download_datasets() first."
            )

        print("[INFO] Loading world map...")
        world: gpd.GeoDataFrame = gpd.read_file(map_path)
    else:
        world = world_map.copy()

<<<<<<< Updated upstream
=======
    # Keep only the columns we need from the shapefile.
    # ISO_A3 is the standard 3-letter code column in Natural Earth.
    # Disputed/unrecognised territories (ISO_A3 = '-99') are kept, but they 
    # won't match any OWID row.
>>>>>>> Stashed changes
    world = world[["ISO_A3", "NAME", "CONTINENT", "geometry"]].copy()

    # Store merged GeoDataFrames in a dictionary keyed by dataset name
    merged: dict[str, gpd.GeoDataFrame] = {}

    # Process each CSV dataset. Merge it with the world map. Raise errors if files or expected columns are missing.
    for name in CSV_DATASETS:
        csv_path = os.path.join(downloads_dir, f"{name}.csv")

        if not os.path.exists(csv_path):
            raise FileNotFoundError(
                f"Dataset '{name}' not found at '{csv_path}'. "
                "Please run download_datasets() first."
            )

        print(f"[INFO] Processing '{name}'...")
        df: pd.DataFrame = pd.read_csv(csv_path)

<<<<<<< Updated upstream
        # --- Normalise key column names to canonical case ----------------------
        # OWID occasionally ships lowercase headers (code/year/entity).
        rename: dict[str, str] = {}
        for col in df.columns:
            if col.lower() == "entity":
                rename[col] = "Entity"
            elif col.lower() == "code":
                rename[col] = "Code"
            elif col.lower() == "year":
                rename[col] = "Year"
        if rename:
            df = df.rename(columns=rename)

        # --- Validate expected columns -----------------------------------------
=======
        # Validate that required columns are present. Raise an error if missing.
>>>>>>> Stashed changes
        required_columns = {"Code", "Year"}
        missing = required_columns - set(df.columns)

        if missing:
            raise ValueError(
                f"Dataset '{name}' is missing expected columns: {missing}. "
                f"Found columns: {list(df.columns)}"
            )

<<<<<<< Updated upstream
        # --- Filter to valid country-level rows only ---------------------------
=======
        # Filter to valid country-level rows only. Drop invalid and NaN codes to avoid pollution of the merge. 
>>>>>>> Stashed changes
        df = df[df["Code"].notna()]
        df = df[df["Code"].astype(str).str.match(r"^[A-Z]{3}$", na=False)]

        # Select only the most recent year of data.
        most_recent_year: int = int(df["Year"].max())
        print(f"         Most recent year for '{name}': {most_recent_year}")
        df_recent: pd.DataFrame = df[df["Year"] == most_recent_year].copy()

<<<<<<< Updated upstream
        # Drop redundant columns before merging (optional)
=======
        # Drop Year and Entity columns before merging.
>>>>>>> Stashed changes
        cols_to_drop = [c for c in ["Year", "Entity"] if c in df_recent.columns]
        if cols_to_drop:
            df_recent = df_recent.drop(columns=cols_to_drop)

        # Merge datasets with countries on country codes. (left = GeoDataFrame so geometry is always preserved)
        merged_gdf: gpd.GeoDataFrame = world.merge(
            df_recent,
            left_on="ISO_A3",
            right_on="Code",
            how="left",
        )

<<<<<<< Updated upstream
        # Drop redundant join key from OWID side (same info as ISO_A3)
=======
        # Drop the redundant 'Code' column
>>>>>>> Stashed changes
        if "Code" in merged_gdf.columns:
            merged_gdf = merged_gdf.drop(columns=["Code"])

        # Store the merged GeoDataFrame in the result dictionary
        merged[name] = merged_gdf
        print(
            f"[OK] '{name}' merged — {merged_gdf.shape[0]} countries, "
            f"{merged_gdf.shape[1]} columns."
        )

    return merged


if __name__ == "__main__":
    download_datasets()