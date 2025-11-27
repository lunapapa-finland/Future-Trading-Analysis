"""
Environment/runtime settings (paths, logging, timezone, ports).
"""

from __future__ import annotations

import os
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _resolve_project_root() -> Path:
    env_root = os.environ.get("PROJECT_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        if p.exists():
            return p

    here = Path(__file__).resolve()
    for parent in [*here.parents]:
        if (parent / "src" / "dashboard").exists():
            return parent
        if (parent / "data").exists() and (parent / "log").exists():
            return parent

    log.warning("PROJECT_ROOT not set; falling back to CWD")
    return Path.cwd()


BASE_DIR = _resolve_project_root()

# Allow path overrides via env, otherwise default under BASE_DIR
LOG_DIR = Path(os.environ.get("LOG_DIR", BASE_DIR / "log"))
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
PERFORMANCE_DIR = Path(os.environ.get("PERFORMANCE_DIR", DATA_DIR / "performance"))
FUTURE_DIR = Path(os.environ.get("FUTURE_DIR", DATA_DIR / "future"))
TEMP_PERF_DIR = Path(os.environ.get("TEMP_PERFORMANCE_DIR", DATA_DIR / "temp_performance"))

# Ensure directories exist
for d in (LOG_DIR, DATA_DIR, PERFORMANCE_DIR, FUTURE_DIR, TEMP_PERF_DIR):
    d.mkdir(parents=True, exist_ok=True)

DEBUG_FLAG = False  # Enable debug mode
PORT = int(os.environ.get("PORT", "8050"))
TIMEZONE = os.environ.get("TIMEZONE", "US/Central")
LOGGING_PATH = LOG_DIR / "app.log"

# UI-facing timeframe options (chart intervals)
TIMEFRAME_OPTIONS = ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]

# Playback speed presets (seconds per bar)
PLAYBACK_SPEEDS = [15, 30, 45, 60]
