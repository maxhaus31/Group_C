"""
main.py
-------
Entry point for Project Okavango.

Run tests (data init / sanity checks):
    python main.py test

Run Streamlit app:
    streamlit run main.py
    python main.py streamlit
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_tests() -> None:
    """Run project data setup and print a short summary."""
    # Import here so normal execution (streamlit mode) doesn't require
    # the full test-only dependency chain at import time.
    from app.data_handler import OkavangoData  # adjust if your class lives elsewhere

    data = OkavangoData()
    print("✅ Project data initialized successfully.")
    print(f"Available datasets: {list(getattr(data, 'DISPLAY_NAMES', {}).keys()) or list(getattr(data, 'merged', {}).keys())}")


def run_streamlit() -> None:
    """Launch the Streamlit UI."""
    app_path = Path(__file__).parent / "app" / "streamlit_app.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Project Okavango")
    parser.add_argument(
        "mode",
        nargs="?",
        default="streamlit",
        choices=["test", "streamlit"],
        help="Run tests or Streamlit app (default: streamlit)",
    )
    args = parser.parse_args()

    if args.mode == "test":
        run_tests()
    else:
        run_streamlit()


if __name__ == "__main__":
    main()
