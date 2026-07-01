"""Run Open Wealth Dashboard with clean environment (no Hermes PATH leak)."""
import os
import sys
from pathlib import Path

# Strip Hermes paths from PYTHONPATH to avoid Python 3.11/3.12 conflicts
hermes_paths = [p for p in os.environ.get("PYTHONPATH", "").split(";")
                if "hermes" in p.lower()]
if hermes_paths:
    for hp in hermes_paths:
        sys.path = [p for p in sys.path if p != hp]

from waitress import serve
from app import app

if __name__ == "__main__":
    print("=" * 55)
    print("  OPEN WEALTH DASHBOARD")
    print("  http://localhost:5000")
    print("=" * 55)
    serve(app, host="0.0.0.0", port=5000, threads=4)
