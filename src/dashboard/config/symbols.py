"""
Symbol catalog and source definitions for data acquisition.

Each symbol entry can carry:
- asset_class: logical grouping (equity/fx/crypto/etc.)
- source: dict describing how to fetch data (type, ticker format, roll rule)
- data_path: CSV path for raw bars (relative to project root by default)
- performance_path: optional performance CSV path override
- enabled: toggle to skip disabled symbols
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

# Defaults used when symbol entries omit explicit values
DEFAULT_EXCHANGE = "CME"
DEFAULT_TIMEZONE = "US/Central"
DEFAULT_PERFORMANCE_FILE = "data/performance/Combined_performance_for_dash_project.csv"

# Month codes for common futures conventions
QUARTERLY_MONTHS = [3, 6, 9, 12]
QUARTERLY_CODES = ["H", "M", "U", "Z"]  # Mar, Jun, Sep, Dec
MONTHLY_MONTHS = list(range(1, 13))
MONTHLY_CODES = ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"]

# Base symbol catalog. Paths are resolved relative to project root.
SYMBOLS: Dict[str, Dict[str, Any]] = {
    "MES": {
        "asset_class": "equity",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "weds_before_third_friday",
            "months": QUARTERLY_MONTHS,
            "codes": QUARTERLY_CODES,
        },
        "data_path": "data/future/MES.csv",
        "performance_path": DEFAULT_PERFORMANCE_FILE,
        "exchange": DEFAULT_EXCHANGE,
        "trading_hours": {"start": "08:30", "end": "15:10", "timezone": DEFAULT_TIMEZONE},
        "expected_rows": 81,
        "calendar": "cme",
        "enabled": True,
    },
    "MNQ": {
        "asset_class": "equity",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "weds_before_third_friday",
            "months": QUARTERLY_MONTHS,
            "codes": QUARTERLY_CODES,
        },
        "data_path": "data/future/MNQ.csv",
        "performance_path": DEFAULT_PERFORMANCE_FILE,
        "exchange": DEFAULT_EXCHANGE,
        "trading_hours": {"start": "08:30", "end": "15:10", "timezone": DEFAULT_TIMEZONE},
        "expected_rows": 81,
        "calendar": "cme",
        "enabled": True,
    },
    "M2K": {
        "asset_class": "equity",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "weds_before_third_friday",
            "months": QUARTERLY_MONTHS,
            "codes": QUARTERLY_CODES,
        },
        "data_path": "data/future/M2K.csv",
        "performance_path": DEFAULT_PERFORMANCE_FILE,
        "exchange": DEFAULT_EXCHANGE,
        "trading_hours": {"start": "08:30", "end": "15:10", "timezone": DEFAULT_TIMEZONE},
        "expected_rows": 81,
        "calendar": "cme",
        "enabled": True,
    },
    "M6E": {
        "asset_class": "fx",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "weds_before_third_friday",
            "months": QUARTERLY_MONTHS,
            "codes": QUARTERLY_CODES,
        },
        "data_path": "data/future/M6E.csv",
        "performance_path": DEFAULT_PERFORMANCE_FILE,
        "exchange": DEFAULT_EXCHANGE,
        "trading_hours": {"start": "08:30", "end": "15:10", "timezone": DEFAULT_TIMEZONE},
        "expected_rows": 81,
        "calendar": "cme",
        "enabled": True,
    },
    "M6B": {
        "asset_class": "fx",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "weds_before_third_friday",
            "months": QUARTERLY_MONTHS,
            "codes": QUARTERLY_CODES,
        },
        "data_path": "data/future/M6B.csv",
        "performance_path": DEFAULT_PERFORMANCE_FILE,
        "exchange": DEFAULT_EXCHANGE,
        "trading_hours": {"start": "08:30", "end": "15:10", "timezone": DEFAULT_TIMEZONE},
        "expected_rows": 81,
        "calendar": "cme",
        "enabled": True,
    },
    "MBT": {
        "asset_class": "crypto",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "last_wednesday",
            "months": MONTHLY_MONTHS,
            "codes": MONTHLY_CODES,
        },
        "data_path": "data/future/MBT.csv",
        "performance_path": DEFAULT_PERFORMANCE_FILE,
        "exchange": DEFAULT_EXCHANGE,
        "trading_hours": {"start": "08:30", "end": "15:10", "timezone": DEFAULT_TIMEZONE},
        "expected_rows": 81,
        "calendar": "cme",
        "enabled": True,
    },
    "MET": {
        "asset_class": "crypto",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "last_wednesday",
            "months": MONTHLY_MONTHS,
            "codes": MONTHLY_CODES,
        },
        "data_path": "data/future/MET.csv",
        "performance_path": DEFAULT_PERFORMANCE_FILE,
        "exchange": DEFAULT_EXCHANGE,
        "trading_hours": {"start": "08:30", "end": "15:10", "timezone": DEFAULT_TIMEZONE},
        "expected_rows": 81,
        "calendar": "cme",
        "enabled": True,
    },
}


def resolve_symbol_catalog(base_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Return symbol catalog with absolute paths resolved under base_dir."""
    catalog: Dict[str, Dict[str, Any]] = {}
    for symbol, cfg in SYMBOLS.items():
        cfg_copy = cfg.copy()
        cfg_copy["data_path"] = str((base_dir / cfg["data_path"]).resolve())
        perf_path = cfg.get("performance_path", DEFAULT_PERFORMANCE_FILE)
        cfg_copy["performance_path"] = str((base_dir / perf_path).resolve())
        cfg_copy["exchange"] = cfg.get("exchange", DEFAULT_EXCHANGE)
        cfg_copy["timezone"] = cfg.get("timezone", DEFAULT_TIMEZONE)
        catalog[symbol] = cfg_copy
    return catalog
