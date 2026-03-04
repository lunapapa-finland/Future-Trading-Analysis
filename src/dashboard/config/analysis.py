"""
Analysis-specific configuration.
"""

import os

INITIAL_NET_LIQ = 10000.0  # USD starting portfolio net liquidation value
RISK_FREE_RATE = 0.02       # Annual risk-free rate for Sharpe/etc
# Start date for portfolio (used for baseline calculations)
PORTFOLIO_START_DATE = "2025-11-01"
# Analysis is always evaluated on CME local time boundaries.
ANALYSIS_TIMEZONE = "US/Central"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except Exception:
        return default


RULE_COMPLIANCE_DEFAULTS = {
    "max_trades_per_day": _int_env("RULE_MAX_TRADES_PER_DAY", 8),
    "max_consecutive_losses": _int_env("RULE_MAX_CONSECUTIVE_LOSSES", 3),
    "max_daily_loss": _float_env("RULE_MAX_DAILY_LOSS", 500.0),
    "big_loss_threshold": _float_env("RULE_BIG_LOSS_THRESHOLD", 200.0),
    "max_trades_after_big_loss": _int_env("RULE_MAX_TRADES_AFTER_BIG_LOSS", 2),
}
