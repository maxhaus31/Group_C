"""
streamlit_app.py
----------------
Streamlit front-end for Project Okavango.

Usage (from project root):
    streamlit run main.py

Features
--------
* Sidebar selector to choose which dataset / world map to display.
* Choropleth world map rendered with GeoPandas + Matplotlib.
* Chart below the map showing the top-5 and bottom-5 countries for the
  selected metric, rendered with Plotly.
"""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import plotly.graph_objects as go
import streamlit as st

matplotlib.use("Agg")  # non-interactive backend required for Streamlit



# Page config
st.set_page_config(
    page_title="Project Okavango 🌿",
    page_icon="🌍",
    layout="wide",
)


# Load data (cached so it only runs once per session)
@st.cache_resource(show_spinner="Downloading & merging datasets — this may take a minute…")
def load_data():  # type: ignore[return]
    """Instantiate OkavangoData once and cache it for the session."""
    # Import here so Streamlit's module cache works correctly
    from app.data_handler import OkavangoData  # noqa: PLC0415

    return OkavangoData()


data = load_data()



# Sidebar Formatting
st.sidebar.image(
    "https://upload.wikimedia.org/wikipedia/commons/d/d0/Okavango_delta_-_Botswana_-_panoramio.jpg",
    use_container_width=True,
    caption="Okavango Delta, Botswana",
)

st.sidebar.title("🌿 Project Okavango")
st.sidebar.markdown("---")
st.sidebar.subheader("Dataset selector")

dataset_options = list(data.DISPLAY_NAMES.keys())
selected_key = st.sidebar.selectbox(
    "Choose a dataset",
    options=dataset_options,
    format_func=lambda k: data.DISPLAY_NAMES[k],
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Data sources:** Our World in Data · Natural Earth  \n"
    "**Team:** Korbinian Dietl · Jonas Knosp · Maximilian Haussmann"
)



# Main area header creation
display_name = data.DISPLAY_NAMES[selected_key]

st.title(f"🌍 {display_name}")
st.markdown(
    f"Showing the **most recent available year** for *{display_name}*. "
    "Use the sidebar to switch between datasets."
)

gdf = data.merged[selected_key]
value_col = data.get_value_column(selected_key)

# Find the most recent year that was used
st.info(
    # f"📊 **Column plotted:** `{value_col}`  |  "
    f"**Countries with data:** {gdf[value_col].notna().sum()} / {len(gdf)}"
)



# World choropleth map

def render_choropleth(gdf_plot, col: str, title: str) -> plt.Figure:
    """Render a choropleth world map using GeoPandas + Matplotlib."""
    fig, ax = plt.subplots(1, 1, figsize=(18, 9), facecolor="#0e1117")
    ax.set_facecolor("#0e1117")

    # Countries with no data — grey background layer
    gdf_plot[gdf_plot[col].isna()].plot(
        ax=ax,
        color="#3a3a3a",
        edgecolor="#555555",
        linewidth=0.3,
    )

    # Colormap selection per dataset type
    cmap_map: dict[str, str] = {
        "annual_change_forest_area": "RdYlGn",   # red = loss, green = gain
        "annual_deforestation": "YlOrRd",         # yellow→red = more deforestation
        "share_land_protected": "YlGn",           # yellow→green = more protected
        "share_land_degraded": "YlOrBr",          # yellow→brown = more degraded
        "forest_area_share": "Greens",            # greens = more forest
    }
    cmap = cmap_map.get(selected_key, "viridis")

    gdf_plot[gdf_plot[col].notna()].plot(
        column=col,
        ax=ax,
        cmap=cmap,
        edgecolor="#222222",
        linewidth=0.3,
        legend=True,
        legend_kwds={
            "label": col.replace("_", " ").title(),
            "orientation": "horizontal",
            "shrink": 0.5,
            "pad": 0.02,
            "fraction": 0.03,
        },
    )

    # Style the legend text/tick labels for dark background
    for text in ax.get_figure().findobj(matplotlib.text.Text):
        text.set_color("white")

    ax.set_title(title, color="white", fontsize=16, pad=12)
    ax.axis("off")
    fig.tight_layout(pad=0)
    return fig


with st.spinner("Rendering map…"):
    fig_map = render_choropleth(gdf, value_col, display_name)
    st.pyplot(fig_map, use_container_width=True)

plt.close("all")

# Top / Bottom bar chart
st.markdown("---")
st.subheader(f"Top 5 & Bottom 5 Countries — {display_name}")

top5, bottom5 = data.top_bottom_countries(selected_key, n=5)

# Friendly label for the axis
axis_label = value_col.replace("_", " ").title()

# Colours — green for top, red for bottom
top_colors = ["#2ecc71"] * 5
bottom_colors = ["#e74c3c"] * 5

fig_bar = go.Figure()

# Bottom-5 (plotted first so they appear on the left)
fig_bar.add_trace(
    go.Bar(
        x=bottom5["NAME"],
        y=bottom5[value_col],
        name="Bottom 5",
        marker_color=bottom_colors,
        text=bottom5[value_col].round(2),
        textposition="outside",
    )
)

# Top-5
fig_bar.add_trace(
    go.Bar(
        x=top5["NAME"],
        y=top5[value_col],
        name="Top 5",
        marker_color=top_colors,
        text=top5[value_col].round(2),
        textposition="outside",
    )
)

fig_bar.update_layout(
    template="plotly_dark",
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font_color="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis_title="Country",
    yaxis_title=axis_label,
    height=420,
    margin=dict(t=40, b=60),
    bargap=0.25,
)

st.plotly_chart(fig_bar, use_container_width=True)


# Raw data expander
with st.expander("🔍 Explore raw merged data"):
    display_cols = ["NAME", "CONTINENT", value_col]
    st.dataframe(
        gdf[display_cols]
        .dropna(subset=[value_col])
        .sort_values(value_col, ascending=False)
        .reset_index(drop=True),
        use_container_width=True,
    )
