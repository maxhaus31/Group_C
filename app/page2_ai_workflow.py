"""
page2_ai_workflow.py
--------------------
Streamlit page 2 for Project Okavango – Part 2.

Features
--------
* Coordinate + zoom selector (lat, lon, zoom sliders + manual input).
* Downloads a satellite tile image from ESRI World Imagery (free, no API key).
* Uses ollama (llava) to describe the image.
* Uses ollama (llama3) to assess environmental risk from the description.
* Caches results in database/images.csv to avoid re-running the pipeline.
* Stores images in images/ directory, keyed by lat_lon_zoom.

Usage
-----
This file is imported by streamlit_app.py and rendered as page 2.
Do NOT run this file directly.
"""

from __future__ import annotations

import csv
import io
import math
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st
import yaml
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from PIL import Image

# ---------------------------------------------------------------------------
# Location helper
# ---------------------------------------------------------------------------

def _reverse_geocode(lat: float, lon: float) -> str:
    """Get city/region name from coordinates using OpenStreetMap Nominatim."""
    try:
        geolocator = Nominatim(user_agent="project_okavango/1.0")
        location = geolocator.reverse(f"{lat}, {lon}", language="en", timeout=5)
        address_parts = location.address.split(",")
        if len(address_parts) >= 2:
            city = address_parts[-3].strip() if len(address_parts) > 2 else address_parts[0].strip()
            country = address_parts[-1].strip()
            return f"{city}, {country}"
        return location.address
    except (GeocoderTimedOut, Exception):
        return f"{lat:.4f}, {lon:.4f}"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent.parent
IMAGES_DIR = ROOT_DIR / "images"
DATABASE_DIR = ROOT_DIR / "database"
DATABASE_CSV = DATABASE_DIR / "images.csv"
MODELS_YAML = ROOT_DIR / "models.yaml"

IMAGES_DIR.mkdir(exist_ok=True)
DATABASE_DIR.mkdir(exist_ok=True)

# Ensure CSV exists with headers
if not DATABASE_CSV.exists():
    DATABASE_CSV.write_text(
        "timestamp,latitude,longitude,zoom,image_path,"
        "image_description,image_prompt,image_model,"
        "text_description,text_prompt,text_model,danger\n"
    )

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load models.yaml config. Falls back to sensible defaults if missing."""
    if MODELS_YAML.exists():
        with open(MODELS_YAML) as f:
            return yaml.safe_load(f)
    # Fallback defaults
    return {
        "image_analysis": {
            "model": "llava:7b",
            "prompt": "Describe this satellite image in detail from an environmental perspective.",
            "temperature": 0.3,
            "max_tokens": 512,
        },
        "risk_assessment": {
            "model": "llama3.2:3b",
            "prompt": (
                "Given this satellite image description, answer YES or NO: "
                "Is there visible environmental danger (deforestation, degradation, pollution)? "
                "Reply with: DANGER: YES/NO and SUMMARY: <one sentence>."
            ),
            "temperature": 0.1,
            "max_tokens": 256,
        },
        "tile_settings": {
            "tile_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "tile_size": 256,
            "default_zoom": 12,
            "default_lat": 48.8566,
            "default_lon": 2.3522,
            "grid_size": 3,
        },
    }


# ---------------------------------------------------------------------------
# ESRI tile helpers
# ---------------------------------------------------------------------------

def _lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert WGS84 lat/lon to (x, y) tile indices at given zoom level."""
    lat_rad = math.radians(lat)
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def fetch_esri_image(lat: float, lon: float, zoom: int, config: dict) -> Image.Image:
    """
    Download a grid of ESRI World Imagery tiles and stitch them into one image.

    Args:
        lat: Latitude (WGS84).
        lon: Longitude (WGS84).
        zoom: Zoom level (1–19).
        config: Tile settings from models.yaml.

    Returns:
        PIL Image of the stitched tile grid.
    """
    tile_cfg = config.get("tile_settings", {})
    url_template: str = tile_cfg.get(
        "tile_url",
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    )
    tile_size: int = int(tile_cfg.get("tile_size", 256))
    grid: int = int(tile_cfg.get("grid_size", 3))

    cx, cy = _lat_lon_to_tile(lat, lon, zoom)
    half = grid // 2

    stitched = Image.new("RGB", (tile_size * grid, tile_size * grid))

    headers = {"User-Agent": "ProjectOkavango/1.0 (educational use)"}

    for row in range(grid):
        for col in range(grid):
            tx = cx - half + col
            ty = cy - half + row
            url = url_template.format(z=zoom, x=tx, y=ty)
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                tile_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            except Exception:
                # Fill missing tile with dark grey
                tile_img = Image.new("RGB", (tile_size, tile_size), color=(50, 50, 50))
            stitched.paste(tile_img, (col * tile_size, row * tile_size))

    return stitched


def _image_key(lat: float, lon: float, zoom: int) -> str:
    """Generate a filesystem-safe key for a lat/lon/zoom combination."""
    return f"{lat:.4f}_{lon:.4f}_z{zoom}"


def save_image(img: Image.Image, lat: float, lon: float, zoom: int) -> Path:
    """Save stitched image to the images/ directory."""
    key = _image_key(lat, lon, zoom)
    path = IMAGES_DIR / f"{key}.png"
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

def _ensure_model(model_name: str) -> None:
    """Pull an ollama model if it isn't already available locally."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if model_name.split(":")[0] not in result.stdout:
            st.info(f"⬇️ Pulling ollama model `{model_name}` — this may take a few minutes…")
            subprocess.run(["ollama", "pull", model_name], check=True)
    except FileNotFoundError:
        st.error(
            "❌ **ollama is not installed or not in PATH.**  \n"
            "Install it from https://ollama.com/ and make sure it is running."
        )
        st.stop()


def describe_image_with_ollama(image_path: Path, config: dict) -> str:
    """
    Send the satellite image to the llava model for a natural language description.

    Args:
        image_path: Path to the PNG file on disk.
        config: Full config dict from models.yaml.

    Returns:
        Text description from the model.
    """
    img_cfg = config["image_analysis"]
    model: str = img_cfg["model"]
    prompt: str = img_cfg["prompt"]

    _ensure_model(model)

    import ollama  # type: ignore[import]  # installed at runtime

    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": [str(image_path)],
            }
        ],
        options={
            "temperature": float(img_cfg.get("temperature", 0.3)),
            "num_predict": int(img_cfg.get("max_tokens", 512)),
        },
    )
    return response["message"]["content"].strip()


def assess_risk_with_ollama(description: str, config: dict) -> tuple[str, bool]:
    """
    Ask a text model to assess environmental risk from the image description.

    Args:
        description: The image description returned by the vision model.
        config: Full config dict from models.yaml.

    Returns:
        Tuple of (full model response text, danger_flag as bool).
    """
    risk_cfg = config["risk_assessment"]
    model: str = risk_cfg["model"]
    prompt: str = risk_cfg["prompt"]

    _ensure_model(model)

    import ollama  # type: ignore[import]

    full_prompt = f"{prompt}\n\nImage description:\n{description}"

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": full_prompt}],
        options={
            "temperature": float(risk_cfg.get("temperature", 0.1)),
            "num_predict": int(risk_cfg.get("max_tokens", 256)),
        },
    )
    text: str = response["message"]["content"].strip()

    # Parse DANGER flag (look for "DANGER: YES" in the response)
    danger_flag = "DANGER: YES" in text.upper()
    return text, danger_flag


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _read_database() -> list[dict]:
    """Read all rows from images.csv."""
    rows: list[dict] = []
    if DATABASE_CSV.exists():
        with open(DATABASE_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    return rows


def _find_cached(lat: float, lon: float, zoom: int) -> dict | None:
    """Return an existing database row for this lat/lon/zoom, or None."""
    key = _image_key(lat, lon, zoom)
    for row in _read_database():
        row_key = _image_key(
            float(row.get("latitude", 0)),
            float(row.get("longitude", 0)),
            int(row.get("zoom", 0)),
        )
        if row_key == key:
            return row
    return None


def _append_to_database(row: dict) -> None:
    """Append a result row to images.csv."""
    fieldnames = [
        "timestamp", "latitude", "longitude", "zoom",
        "image_path", "image_description", "image_prompt", "image_model",
        "text_description", "text_prompt", "text_model", "danger",
    ]
    file_exists = DATABASE_CSV.exists()
    with open(DATABASE_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Main render function (called from streamlit_app.py)
# ---------------------------------------------------------------------------

def render() -> None:
    """Render Page 2 – AI Environmental Risk Workflow."""

    config = load_config()
    if config is None:
        config = {}
    tile_cfg = config.get("tile_settings", {})

    st.title("🛰️ AI Environmental Risk Analyser")
    st.markdown(
        "Select a location on Earth, fetch a satellite image, and let AI assess "
        "whether the area shows signs of **environmental danger**."
    )

    # -----------------------------------------------------------------------
    # Sidebar controls
    # -----------------------------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 Location Settings")

    lat = st.sidebar.number_input(
        "Latitude",
        min_value=-90.0,
        max_value=90.0,
        value=float(tile_cfg.get("default_lat", 48.8566)),
        step=0.01,
        format="%.4f",
    )
    lon = st.sidebar.number_input(
        "Longitude",
        min_value=-180.0,
        max_value=180.0,
        value=float(tile_cfg.get("default_lon", 2.3522)),
        step=0.01,
        format="%.4f",
    )
    zoom = st.sidebar.slider(
        "Zoom level",
        min_value=5,
        max_value=18,
        value=int(tile_cfg.get("default_zoom", 12)),
        help="Higher zoom = more detail but smaller area covered.",
    )

    run_btn = st.sidebar.button("🚀 Analyse Location", type="primary", use_container_width=True)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"**Image model:** `{config.get('image_analysis', {}).get('model', 'llava:7b')}`  \n"
        f"**Risk model:** `{config.get('risk_assessment', {}).get('model', 'llama3.2:3b')}`  \n"
        "_Edit `models.yaml` to change._"
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Team:** Korbinian Dietl · Jonas Knosp · Maximilian Haussmann  \n"
        "**Data:** Our World in Data · Natural Earth · ESRI"
    )

    # -----------------------------------------------------------------------
    # Check cache before running pipeline
    # -----------------------------------------------------------------------
    cached = _find_cached(lat, lon, zoom)

    if cached and not run_btn:
        st.info("⚡ **Loaded from cache** — this location was already analysed.")
        _display_results(
            image_path=Path(cached["image_path"]),
            description=cached["image_description"],
            risk_text=cached["text_description"],
            danger=cached["danger"].strip().upper() == "Y",
            lat=lat,
            lon=lon,
        )
        return

    if not run_btn:
        st.markdown(
            "👈 Set your coordinates and zoom in the sidebar, then click **Analyse Location**."
        )
        _show_quickstart_examples()
        return

    # -----------------------------------------------------------------------
    # Run the full pipeline
    # -----------------------------------------------------------------------
    with st.status("Running AI analysis pipeline…", expanded=True) as status:

        # Step 1: fetch satellite image
        st.write("📡 Fetching satellite image from ESRI World Imagery…")
        try:
            img = fetch_esri_image(lat, lon, zoom, config)
        except Exception as exc:
            st.error(f"Failed to fetch image: {exc}")
            return
        image_path = save_image(img, lat, lon, zoom)
        st.write(f"✅ Image saved to `{image_path.relative_to(ROOT_DIR)}`")

        # Step 2: describe image
        st.write("🔍 Describing image with vision model…")
        try:
            description = describe_image_with_ollama(image_path, config)
        except Exception as exc:
            st.error(f"Image description failed: {exc}")
            return
        st.write("✅ Image description complete.")

        # Step 3: assess risk
        st.write("⚠️ Assessing environmental risk…")
        try:
            risk_text, danger = assess_risk_with_ollama(description, config)
        except Exception as exc:
            st.error(f"Risk assessment failed: {exc}")
            return
        st.write("✅ Risk assessment complete.")

        # Step 4: save to database
        _append_to_database(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "latitude": lat,
                "longitude": lon,
                "zoom": zoom,
                "image_path": str(image_path),
                "image_description": description,
                "image_prompt": config["image_analysis"]["prompt"],
                "image_model": config["image_analysis"]["model"],
                "text_description": risk_text,
                "text_prompt": config["risk_assessment"]["prompt"],
                "text_model": config["risk_assessment"]["model"],
                "danger": "Y" if danger else "N",
            }
        )
        status.update(label="✅ Pipeline complete!", state="complete")

    _display_results(image_path, description, risk_text, danger, lat, lon)


def _display_results(
    image_path: Path,
    description: str,
    risk_text: str,
    danger: bool,
    lat: float = None,
    lon: float = None,
) -> None:
    """Render the image, description, and risk assessment side by side."""

    # Location header
    if lat is not None and lon is not None:
        location = _reverse_geocode(lat, lon)
        st.markdown(f"### 📍 {location}")
        st.caption(f"Coordinates: {lat:.4f}, {lon:.4f}")
        st.markdown("---")

    # Risk banner at the top
    if danger:
        st.error(
            "🚨 **ENVIRONMENTAL RISK DETECTED** — "
            "The AI flagged this area as potentially at risk."
        )
    else:
        st.success(
            "✅ **No significant environmental risk detected** — "
            "The area appears to be in good condition."
        )

    st.markdown("---")
    col_img, col_desc = st.columns([1, 1], gap="large")

    with col_img:
        st.subheader("🛰️ Satellite Image")
        if image_path.exists():
            st.image(str(image_path), use_container_width=True)
        else:
            st.warning("Image file not found.")

    with col_desc:
        st.subheader("📝 Image Description")
        st.markdown(description)

    st.markdown("---")
    st.subheader("🔬 Environmental Risk Assessment")

    # Parse and display individual question answers if present
    lines = risk_text.splitlines()
    q_lines = [l for l in lines if l.strip().startswith("Q")]
    summary_lines = [l for l in lines if "SUMMARY:" in l.upper()]
    other_lines = [l for l in lines if l not in q_lines and "DANGER:" not in l.upper() and l not in summary_lines]

    if q_lines:
        questions = {
            "Q1": "Deforestation / tree cover loss",
            "Q2": "Soil erosion / land degradation",
            "Q3": "Urban sprawl on natural areas",
            "Q4": "Water body changes / pollution",
            "Q5": "Habitat fragmentation",
        }
        cols = st.columns(len(q_lines))
        for i, line in enumerate(q_lines):
            qkey = line.split(":")[0].strip()
            answer = "YES" if "YES" in line.upper() else "NO"
            label = questions.get(qkey, qkey)
            with cols[i]:
                if answer == "YES":
                    st.metric(label=label, value="⚠️ YES")
                else:
                    st.metric(label=label, value="✅ NO")
    else:
        st.markdown(risk_text)

    if summary_lines:
        st.info(summary_lines[0].replace("SUMMARY:", "**Summary:**"))

    with st.expander("📄 Full model response"):
        st.text(risk_text)


def _show_quickstart_examples() -> None:
    """Show a few preset interesting locations the user can jump to."""
    st.markdown("### 🌍 Quick-start locations")
    st.markdown("These presets let you quickly test the pipeline on known areas:")

    examples = [
        ("🌲 Amazon Rainforest", -3.47, -62.21, 12),
        ("🏜️ Sahara Desert edge", 15.37, 2.01, 11),
        ("🌿 Borneo deforestation", 1.29, 114.57, 13),
        ("🏙️ São Paulo sprawl", -23.55, -46.63, 12),
        ("🌊 Aral Sea shrinkage", 45.0, 60.0, 10),
    ]

    cols = st.columns(len(examples))
    for col, (label, e_lat, e_lon, e_zoom) in zip(cols, examples):
        with col:
            st.markdown(f"**{label}**")
            st.caption(f"lat={e_lat}, lon={e_lon}, zoom={e_zoom}")
