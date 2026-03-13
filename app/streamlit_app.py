"""
streamlit_app.py
----------------
Streamlit front-end for Project Okavango.

Usage (from project root):
    streamlit run main.py

Pages
-----
1. 🌍 World Maps       — choropleth maps + top/bottom country charts (Part 1)
2. 🛰️ AI Risk Analyser — satellite imagery + ollama environmental risk (Part 2)
"""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import streamlit as st

matplotlib.use("Agg")  # non-interactive backend required for Streamlit

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Project Okavango 🌿",
    page_icon="🌍",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Page navigation
# ---------------------------------------------------------------------------
PAGES = {
    "🌍 World Maps": "maps",
    "🛰️ AI Risk Analyser": "ai",
}

st.sidebar.image(
    "https://upload.wikimedia.org/wikipedia/commons/d/d0/Okavango_delta_-_Botswana_-_panoramio.jpg",
    use_container_width=True,
    caption="Okavango Delta, Botswana",
)
st.sidebar.title("🌿 Project Okavango")
st.sidebar.markdown("---")

st.sidebar.markdown("### Menu")
selected_page = st.sidebar.radio(
    "Navigate",
    options=list(PAGES.keys()),
    label_visibility="collapsed",
)

st.sidebar.markdown(
    """
    <style>
    div[role='radiogroup'] label {
        font-weight: 600;
        font-size: 1rem;
        padding: 6px 0px;
        cursor: pointer;
    }
    div[role='radiogroup'] label:hover {
        text-decoration: underline;
    }
    div[role='radiogroup'] > label > div:first-child {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Route to the correct page
# ---------------------------------------------------------------------------
if PAGES[selected_page] == "maps":
    # -----------------------------------------------------------------------
    # PAGE 1 — World Maps (Part 1, unchanged)
    # -----------------------------------------------------------------------
    import matplotlib.colors as mcolors
    import numpy as np
    import plotly.graph_objects as go

    @st.cache_resource(show_spinner="Downloading & merging datasets — this may take a minute…")
    def load_data():  # type: ignore[return]
        from app.data_handler import OkavangoData  # noqa: PLC0415
        return OkavangoData()

    data = load_data()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Dataset selector")
    dataset_options = list(data.DISPLAY_NAMES.keys())
    selected_key = st.sidebar.selectbox(
        "Choose a dataset",
        options=dataset_options,
        format_func=lambda k: data.DISPLAY_NAMES[k],
    )

    display_name = data.DISPLAY_NAMES[selected_key]
    st.title(f"🌍 {display_name}")
    st.markdown(
        f"Showing the **most recent available year** for *{display_name}*. "
        "Use the sidebar to switch between datasets."
    )

    gdf = data.merged[selected_key]
    value_col = data.get_value_column(selected_key)

    st.info(f"**Countries with data:** {gdf[value_col].notna().sum()} / {len(gdf)}")

    def render_choropleth(gdf_plot, col: str, title: str) -> plt.Figure:
        fig, ax = plt.subplots(1, 1, figsize=(18, 9), facecolor="#0e1117")
        ax.set_facecolor("#0e1117")
        gdf_plot[gdf_plot[col].isna()].plot(ax=ax, color="#3a3a3a", edgecolor="#555555", linewidth=0.3)
        cmap_map: dict[str, str] = {
            "annual_change_forest_area": "RdYlGn",
            "annual_deforestation": "YlOrRd",
            "share_land_protected": "YlGn",
            "share_land_degraded": "YlOrBr",
            "forest_area_share": "Greens",
        }
        cmap = cmap_map.get(selected_key, "viridis")
        gdf_plot[gdf_plot[col].notna()].plot(
            column=col, ax=ax, cmap=cmap, edgecolor="#222222", linewidth=0.3,
            legend=True,
            legend_kwds={"label": col.replace("_", " ").title(), "orientation": "horizontal", "shrink": 0.5, "pad": 0.02, "fraction": 0.03},
        )
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

    st.markdown("---")
    st.subheader(f"Top 5 & Bottom 5 Countries — {display_name}")
    top5, bottom5 = data.top_bottom_countries(selected_key, n=5)
    axis_label = value_col.replace("_", " ").title()

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(x=bottom5["NAME"], y=bottom5[value_col], name="Bottom 5", marker_color=["#e74c3c"] * 5, text=bottom5[value_col].round(2), textposition="outside"))
    fig_bar.add_trace(go.Bar(x=top5["NAME"], y=top5[value_col], name="Top 5", marker_color=["#2ecc71"] * 5, text=top5[value_col].round(2), textposition="outside"))
    fig_bar.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font_color="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="Country", yaxis_title=axis_label, height=420, margin=dict(t=40, b=60), bargap=0.25)
    st.plotly_chart(fig_bar, use_container_width=True)

    with st.expander("🔍 Explore raw merged data"):
        display_cols = ["NAME", "CONTINENT", value_col]
        st.dataframe(gdf[display_cols].dropna(subset=[value_col]).sort_values(value_col, ascending=False).reset_index(drop=True), use_container_width=True)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Team:** Korbinian Dietl · Jonas Knosp · Maximilian Haussmann  \n"
        "<br>"
        "**Data:** Our World in Data · Natural Earth · ESRI",
        unsafe_allow_html=True,
    )

else:
    # -----------------------------------------------------------------------
    # PAGE 2 — AI Environmental Risk Analyser (Part 2)
    # -----------------------------------------------------------------------
    from app.page2_ai_workflow import render  # noqa: PLC0415
    render()
