from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_tests() -> None:
    """
    Test the full data pipeline without launching UI.
    1. OkavangoData() initializes successfully
    2. All datasets are available and accessible
    3. No import/runtime errors in data loading
    """
    from app.data_handler import OkavangoData  # adjust if your class lives elsewhere

    data = OkavangoData()
    print("Project data initialized successfully.")
    print(f"Available datasets: {list(getattr(data, 'DISPLAY_NAMES', {}).keys()) or list(getattr(data, 'merged', {}).keys())}")

def run_streamlit() -> None:
    """
    Launch the Streamlit web UI by pointing to streamlit_app.py.
    Expects app/streamlit_app.py to exist with complete UI implementation.
    """
    app_path = Path(__file__).parent / "app" / "streamlit_app.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path)],
        check=True,
    )

def main() -> None:
    """
    CLI entry point with test or streamlit modes.
    """
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
