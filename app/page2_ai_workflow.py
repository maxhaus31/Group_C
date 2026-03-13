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
import json
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


def _geocode_location(location_name: str) -> tuple[float, float] | None:
    """Convert location name to (lat, lon) coordinates using Nominatim."""
    try:
        geolocator = Nominatim(user_agent="project_okavango/1.0")
        location = geolocator.geocode(location_name, timeout=5)
        if location:
            return (location.latitude, location.longitude)
    except (GeocoderTimedOut, Exception):
        pass
    return None


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent.parent
IMAGES_DIR = ROOT_DIR / "images"
DATABASE_DIR = ROOT_DIR / "database"
DATABASE_CSV = DATABASE_DIR / "images.csv"
SEARCH_HISTORY_JSON = DATABASE_DIR / "search_history.json"
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


def _load_search_history() -> list[dict]:
    """Load search history from JSON file."""
    if SEARCH_HISTORY_JSON.exists():
        try:
            with open(SEARCH_HISTORY_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_search_history_entry(location_name: str, lat: float, lon: float, zoom: int) -> None:
    """Save a new search history entry to JSON file."""
    history = _load_search_history()
    
    # Check if this location already exists (deduplicate)
    key = _image_key(lat, lon, zoom)
    history = [h for h in history if _image_key(float(h.get("latitude", 0)), float(h.get("longitude", 0)), int(h.get("zoom", 0))) != key]
    
    # Add the new entry at the beginning
    new_entry = {
        "location_name": location_name,
        "latitude": lat,
        "longitude": lon,
        "zoom": zoom,
        "timestamp": datetime.utcnow().isoformat(),
    }
    history.insert(0, new_entry)
    
    # Keep only last 20 searches
    history = history[:20]
    
    # Write back to file
    with open(SEARCH_HISTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _get_search_history(limit: int = 6) -> list[dict]:
    """Get recently searched locations from JSON file."""
    history = _load_search_history()
    return history[:limit]


# ---------------------------------------------------------------------------
# Main render function (called from streamlit_app.py)
# ---------------------------------------------------------------------------

def render() -> None:
    """Render Page 2 – AI Environmental Risk Workflow."""

    # Initialize session state for presets
    if "run_preset" not in st.session_state:
        st.session_state.run_preset = False

    config = load_config()
    if config is None:
        config = {}
    tile_cfg = config.get("tile_settings", {})

    # Clickable header button to reset and go back to main
    col1, col2 = st.columns([0.85, 0.15])
    with col1:
        st.title("🛰️ AI Environmental Risk Analyser")
    with col2:
        if st.button("↩️ Back", help="Return to main page", key="header_back", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    st.markdown(
        "Select a location on Earth, fetch a satellite image, and let AI assess "
        "whether the area shows signs of **environmental danger**."
    )

    # -----------------------------------------------------------------------
    # Sidebar controls
    # -----------------------------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 Location Settings")

    # Use preset coordinates if a preset was clicked, otherwise use sidebar inputs
    default_lat = float(tile_cfg.get("default_lat", 48.8566))
    default_lon = float(tile_cfg.get("default_lon", 2.3522))
    default_zoom = int(tile_cfg.get("default_zoom", 12))

    if st.session_state.run_preset:
        lat = st.session_state.preset_lat
        lon = st.session_state.preset_lon
        zoom = st.session_state.preset_zoom
    else:
        # Location search field
        location_search = st.sidebar.text_input(
            "🔍 Search for a location",
            placeholder="e.g., London, Paris, Tokyo...",
            help="Type a location name and press Enter to auto-fill coordinates",
        )
        
        if location_search:
            with st.sidebar.spinner("🔍 Finding coordinates..."):
                coords = _geocode_location(location_search)
                if coords:
                    default_lat, default_lon = coords
                    st.sidebar.success(f"✅ Found: {coords[0]:.4f}, {coords[1]:.4f}")
                else:
                    st.sidebar.error(f"❌ Location '{location_search}' not found")
        
        lat = st.sidebar.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=default_lat,
            step=0.01,
            format="%.4f",
        )
        lon = st.sidebar.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=default_lon,
            step=0.01,
            format="%.4f",
        )
        zoom = st.sidebar.slider(
            "Zoom level",
            min_value=5,
            max_value=18,
            value=default_zoom,
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
    
    # Check if we should run the pipeline (either button click or preset)
    should_run = run_btn or st.session_state.run_preset

    if cached and not should_run:
        st.info("⚡ **Loaded from cache** — this location was already analysed.")
        _display_results(
            image_path=Path(cached["image_path"]),
            description=cached["image_description"],
            risk_text=cached["text_description"],
            danger=cached["danger"].strip().upper() == "Y",
            lat=lat,
            lon=lon,
            zoom=zoom,
        )
        return

    if not should_run:
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

    # Save to search history with location name
    location_name = _reverse_geocode(lat, lon)
    _save_search_history_entry(location_name, lat, lon, zoom)
    
    _display_results(image_path, description, risk_text, danger, lat, lon, zoom)
    
    # Reset preset flag after displaying results
    st.session_state.run_preset = False


def _display_results(
    image_path: Path,
    description: str,
    risk_text: str,
    danger: bool,
    lat: float = None,
    lon: float = None,
    zoom: int = 12,
) -> None:
    """Render the image, description, and risk assessment with tabs and metrics."""

    # Location header with metrics card
    if lat is not None and lon is not None:
        location = _reverse_geocode(lat, lon)
        st.markdown(f"### 📍 {location}")
        
        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric("Latitude", f"{lat:.4f}")
        with metric_cols[1]:
            st.metric("Longitude", f"{lon:.4f}")
        with metric_cols[2]:
            st.metric("Zoom Level", zoom)
        with metric_cols[3]:
            st.metric("Date", datetime.utcnow().strftime("%Y-%m-%d"))
        st.markdown("---")

    # Risk banner with severity colors
    if danger:
        st.error(
            "🚨 **ENVIRONMENTAL RISK DETECTED**  \n"
            "The AI identified visible environmental degradation or deforestation."
        )
    else:
        st.success(
            "✅ **Good Environmental Status**  \n"
            "No significant environmental risk detected."
        )

    st.markdown("---")
    
    # Organized tabbed interface
    tab1, tab2, tab3 = st.tabs(["📊 Overview", "📋 Full Analysis", "🔧 Details"])
    
    with tab1:
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
        st.subheader("⚠️ Risk Summary")
        summary_lines = [l for l in risk_text.splitlines() if "SUMMARY:" in l.upper()]
        if summary_lines:
            st.info(summary_lines[0].replace("SUMMARY:", "").strip())
        else:
            st.write(risk_text[:200] + "..." if len(risk_text) > 200 else risk_text)
    
    with tab2:
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

        with st.expander("📄 Full AI Response"):
            st.text(risk_text)
    
    with tab3:
        st.subheader("🤖 Analysis Details")
        with st.expander("📌 Image Analysis Model", expanded=False):
            st.code("Model: llava:7b (Vision)\nPurpose: Satellite image interpretation\nTemperature: 0.3 (deterministic)", language="bash")
        
        with st.expander("📌 Risk Assessment Model", expanded=False):
            st.code("Model: llama3.2:3b (Text)\nPurpose: Environmental risk analysis\nTemperature: 0.1 (very deterministic)", language="bash")
        
        with st.expander("📍 Image Information", expanded=False):
            st.write(f"**Path:** `{image_path.relative_to(ROOT_DIR)}`")
            if image_path.exists():
                st.write(f"**File size:** {image_path.stat().st_size / 1024:.1f} KB")
                st.write(f"**Modified:** {datetime.fromtimestamp(image_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")


def _show_quickstart_examples() -> None:
    """Show a few preset interesting locations with clickable Get Report buttons."""
    st.markdown("### 🌍 Quick-start locations")
    st.markdown("Click **Get Report** on any location to instantly analyze it:")

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
            st.caption(f"`{e_lat:.2f}, {e_lon:.2f}`")
            if st.button(
                "📊 Get Report",
                key=f"preset_{e_lat}_{e_lon}_{e_zoom}",
                use_container_width=True,
            ):
                st.session_state.preset_lat = e_lat
                st.session_state.preset_lon = e_lon
                st.session_state.preset_zoom = e_zoom
                st.session_state.run_preset = True
                st.rerun()
    
    # Show search history if available
    st.markdown("---")
    history = _get_search_history(limit=6)
    if history:
        st.markdown("### 🕐 Search History")
        st.markdown("Quick access to your recently analyzed locations:")
        
        hist_cols = st.columns(len(history))
        for idx, row in enumerate(history):
            try:
                h_lat = float(row.get("latitude", 0))
                h_lon = float(row.get("longitude", 0))
                h_zoom = int(row.get("zoom", 0))
                h_timestamp = row.get("timestamp", "Unknown")
                location_name = row.get("location_name", "Unknown Location")  # Use stored name
                
                # Format friendly timestamp
                try:
                    from datetime import datetime as dt
                    ts = dt.fromisoformat(h_timestamp).strftime("%b %d, %H:%M")
                except:
                    ts = h_timestamp[:10] if len(h_timestamp) > 10 else h_timestamp
                
                with hist_cols[idx]:
                    st.markdown(f"**{location_name}**")
                    st.caption(f"`{h_lat:.2f}, {h_lon:.2f}` • {ts}")
                    if st.button(
                        "📊 View Report",
                        key=f"history_{h_lat}_{h_lon}_{h_zoom}_{idx}",
                    ):
                        st.session_state.preset_lat = h_lat
                        st.session_state.preset_lon = h_lon
                        st.session_state.preset_zoom = h_zoom
                        st.session_state.run_preset = True
                        st.rerun()
            except (ValueError, TypeError):
                continue
    else:
        st.markdown(":gray-background[_No search history yet. Analyze a location to get started!_]")
