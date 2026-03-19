from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from dashboard.config.env import DATA_DIR, FUTURE_DIR, PERFORMANCE_DIR, METADATA_DIR
from dashboard.config.app_config import public_app_config
from dashboard.config.settings import (
    TAXONOMY_CSV,
    PERFORMANCE_CSV,
    JOURNAL_LIVE_CSV,
    JOURNAL_ADJUSTMENTS_CSV,
    JOURNAL_MATCHES_CSV,
    CONTRACT_SPECS_CSV,
    DAY_PLAN_CSV,
)
from dashboard.services.portfolio import CASHFLOW_CSV, TRADE_SUM_CSV


def _csv_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "rows": 0,
        "columns": [],
        "readable": False,
    }
    if not path.exists():
        return info
    try:
        df = pd.read_csv(path)
        info["rows"] = int(len(df))
        info["columns"] = [str(c) for c in df.columns]
        info["readable"] = True
    except Exception:
        info["readable"] = False
    return info


def runtime_manifest() -> dict[str, Any]:
    return {
        "app_config": public_app_config(),
        "roots": {
            "data_dir": str(DATA_DIR),
            "future_dir": str(FUTURE_DIR),
            "performance_dir": str(PERFORMANCE_DIR),
            "metadata_dir": str(METADATA_DIR),
        },
        "sources": {
            "performance_sum": _csv_info(Path(PERFORMANCE_CSV)),
            "journal_live": _csv_info(Path(JOURNAL_LIVE_CSV)),
            "journal_adjustments": _csv_info(Path(JOURNAL_ADJUSTMENTS_CSV)),
            "journal_matches": _csv_info(Path(JOURNAL_MATCHES_CSV)),
            "taxonomy": _csv_info(Path(TAXONOMY_CSV)),
            "contract_specs": _csv_info(Path(CONTRACT_SPECS_CSV)),
            "day_plan": _csv_info(Path(DAY_PLAN_CSV)),
            "cashflow": _csv_info(Path(CASHFLOW_CSV)),
            "trade_sum": _csv_info(Path(TRADE_SUM_CSV)),
        },
    }
