from __future__ import annotations

import csv
import logging
from pathlib import Path

from dashboard.config.settings import (
    PERFORMANCE_CSV,
    TRADE_LABELS_CSV,
    TRADE_TAG_TAXONOMY_CSV,
    DAY_PLAN_TAXONOMY_CSV,
    CONTRACT_SPECS_CSV,
    DAY_PLAN_CSV,
    CASHFLOW_CSV,
    TRADE_SUM_CSV,
)

log = logging.getLogger(__name__)


CSV_SCHEMAS: dict[str, list[str]] = {
    PERFORMANCE_CSV: [
        "trade_id",
        "YearMonth",
        "TradeDay",
        "DayOfWeek",
        "HourOfDay",
        "ContractName",
        "IntradayIndex",
        "EnteredAt",
        "ExitedAt",
        "EntryPrice",
        "ExitPrice",
        "Fees",
        "PnL(Net)",
        "Size",
        "Type",
        "TradeDuration",
        "WinOrLoss",
        "Streak",
        "Comment",
        "Phase",
        "Context",
        "Setup",
        "SignalBar",
        "TradeIntent",
    ],
    TRADE_LABELS_CSV: ["trade_id", "Phase", "Context", "Setup", "SignalBar", "TradeIntent"],
    TRADE_TAG_TAXONOMY_CSV: ["Field", "Value", "Hint", "SortOrder", "Enabled"],
    DAY_PLAN_TAXONOMY_CSV: ["Field", "Value", "Hint", "SortOrder", "Enabled"],
    CONTRACT_SPECS_CSV: ["symbol", "point_value", "tick_size", "currency", "exchange"],
    DAY_PLAN_CSV: [
        "Date",
        "Bias",
        "ExpectedDayType",
        "ActualDayType",
        "KeyLevelsHTFContext",
        "PrimaryPlan",
        "AvoidancePlan",
        "UpdatedAt",
    ],
    CASHFLOW_CSV: ["event_id", "date", "amount", "reason", "created_at"],
    TRADE_SUM_CSV: ["date", "trade_pnl", "updated_at"],
}


def ensure_required_csvs() -> list[str]:
    created: list[str] = []
    for raw_path, columns in CSV_SCHEMAS.items():
        path = Path(raw_path)
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
        created.append(str(path))
    if created:
        log.info("Initialized missing CSV files: %s", ", ".join(created))
    return created
