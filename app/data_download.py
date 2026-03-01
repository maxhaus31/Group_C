import os
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "downloads")

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
    file containing a shapefile and can be loaded with geopandas directly:
        world = gpd.read_file("downloads/map_dataset.zip")

    Args:
        downloads_dir: Path to the directory where files will be saved.
                       Defaults to the standard DOWNLOADS_DIR constant.
    """
    os.makedirs(downloads_dir, exist_ok=True)

    for name, url in DATASETS.items():
        extension = ".zip" if url.endswith(".zip") else ".csv"
        file_path = os.path.join(downloads_dir, f"{name}{extension}")

        if os.path.exists(file_path):
            print(f"[SKIP] {name} already downloaded.")
            continue

        print(f"[DOWNLOADING] {name}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with open(file_path, "wb") as f:
            f.write(response.content)

        print(f"[OK] {name} saved to {file_path}")


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
    """
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

    world = world[["ISO_A3", "NAME", "CONTINENT", "geometry"]].copy()

    merged: dict[str, gpd.GeoDataFrame] = {}

    for name in CSV_DATASETS:
        csv_path = os.path.join(downloads_dir, f"{name}.csv")

        if not os.path.exists(csv_path):
            raise FileNotFoundError(
                f"Dataset '{name}' not found at '{csv_path}'. "
                "Please run download_datasets() first."
            )

        print(f"[INFO] Processing '{name}'...")
        df: pd.DataFrame = pd.read_csv(csv_path)

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
        required_columns = {"Code", "Year"}
        missing = required_columns - set(df.columns)
        if missing:
            raise ValueError(
                f"Dataset '{name}' is missing expected columns: {missing}. "
                f"Found columns: {list(df.columns)}"
            )

        # --- Filter to valid country-level rows only ---------------------------
        df = df[df["Code"].notna()]
        df = df[df["Code"].astype(str).str.match(r"^[A-Z]{3}$", na=False)]

        # --- Select the most recent year dynamically ---------------------------
        most_recent_year: int = int(df["Year"].max())
        print(f"         Most recent year for '{name}': {most_recent_year}")
        df_recent: pd.DataFrame = df[df["Year"] == most_recent_year].copy()

        # Drop redundant columns before merging (optional)
        cols_to_drop = [c for c in ["Year", "Entity"] if c in df_recent.columns]
        if cols_to_drop:
            df_recent = df_recent.drop(columns=cols_to_drop)

        # --- Merge (left = GeoDataFrame so geometry is always preserved) -------
        merged_gdf: gpd.GeoDataFrame = world.merge(
            df_recent,
            left_on="ISO_A3",
            right_on="Code",
            how="left",
        )

        # Drop redundant join key from OWID side (same info as ISO_A3)
        if "Code" in merged_gdf.columns:
            merged_gdf = merged_gdf.drop(columns=["Code"])

        merged[name] = merged_gdf
        print(
            f"[OK] '{name}' merged — {merged_gdf.shape[0]} countries, "
            f"{merged_gdf.shape[1]} columns."
        )

    return merged


if __name__ == "__main__":
    download_datasets()