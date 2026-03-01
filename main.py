"""
main.py
-------
Entry point for Project Okavango.

Test data functions:
    python main.py test

Run Streamlit app:
    streamlit run main.py    OR    python main.py streamlit
"""

import argparse
import subprocess
import sys
from pathlib import Path

from app import ProjectData


def run_tests() -> None:
    """Run project data setup and print summary."""
    project_data = ProjectData()
    print("Project data initialized successfully.")
    print(f"Loaded raw datasets: {list(project_data.raw_datasets.keys())}")
    print(f"Loaded merged datasets: {list(project_data.merged_datasets.keys())}")


def run_streamlit() -> None:
    """Streamlit app with proper map."""
    import streamlit as st
    from app import ProjectData
    import geopandas as gpd

    st.title("🌍 Project Okavango")

    project_data = ProjectData()
    dataset_name = st.selectbox(
        "Choose dataset:",
        options=list(project_data.merged_datasets.keys())
    )

    gdf = project_data.merged_datasets[dataset_name].copy()
    st.write("Columns:", list(gdf.columns))  # ← ADD THIS

    metric_cols = [col for col in gdf.columns if dataset_name.lower() in col.lower()]
    if not metric_cols:
        st.error(f"No column found matching '{dataset_name}'")
    else:
        metric_col = metric_cols[0]

        # Extract lat/lon
        gdf['lat'] = gdf.geometry.centroid.y
        gdf['lon'] = gdf.geometry.centroid.x

        st.map(gdf[["lat", "lon", metric_col]])

        st.subheader("Top 10 countries")
        st.dataframe(
            gdf.nlargest(10, metric_col)[["NAME", metric_col, "CONTINENT"]]
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Project Okavango")
    parser.add_argument(
        "mode", nargs="?", default="streamlit",
        choices=["test", "streamlit"],
        help="Run tests or Streamlit app (default: streamlit)"
    )
    args = parser.parse_args()

    if args.mode == "test":
        run_tests()
    else:
        run_streamlit()


if __name__ == "__main__":
    main()


