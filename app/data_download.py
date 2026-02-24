import os
import requests

import geopandas as gpd
world = gpd.read_file("ne_110m_admin_0_countries.zip")

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "downloads")

DATASETS = {
    "annual_change_forest_area": "https://ourworldindata.org/grapher/annual-change-forest-area.csv?v=1&csvType=full&useColumnShortNames=true",
    "annual_deforestation": "https://ourworldindata.org/grapher/annual-deforestation.csv?v=1&csvType=full&useColumnShortNames=true",
    "share_land_protected": "https://ourworldindata.org/grapher/terrestrial-protected-areas.csv?v=1&csvType=full&useColumnShortNames=true",
    "share_land_degraded": "https://ourworldindata.org/grapher/share-degraded-land.csv?v=1&csvType=full&useColumnShortNames=true",
    # 5th dataset added. Change if needed
    "forest_area_share": "https://ourworldindata.org/grapher/forest-area-as-share-of-land-area.csv?v=1&csvType=full&useColumnShortNames=true",
    # Fix the map dataset URL
}


def download_datasets(downloads_dir: str = DOWNLOADS_DIR) -> None:
    """
    Downloads all required datasets into the downloads directory.
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

# test commit