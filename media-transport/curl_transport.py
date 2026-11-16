"""Compatibility import for old tooling; the Railway copy is now self-contained."""
from pathlib import Path
import runpy

globals().update(runpy.run_path(str(Path(__file__).resolve().parents[1] / "python-origin" / "curl_transport.py")))
