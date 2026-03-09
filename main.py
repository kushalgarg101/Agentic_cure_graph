"""Convenience entrypoint for local execution via `uv run main.py`."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from github_viz.cli import app

if __name__ == "__main__":
    app()
