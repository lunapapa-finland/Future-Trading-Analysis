from __future__ import annotations

import csv
import logging
from pathlib import Path
import pandas as pd

from dashboard.config.settings import (
    PERFORMANCE_CSV,
    TRADE_LABELS_CSV,
    JOURNAL_LIVE_CSV,
    JOURNAL_ADJUSTMENTS_CSV,
    JOURNAL_MATCHES_CSV,
    TAXONOMY_CSV,
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
    JOURNAL_LIVE_CSV: [
        "journal_id",
        "TradeDay",
        "SeqInDay",
        "ContractName",
        "Phase",
        "Context",
        "Setup",
        "SignalBar",
        "TradeIntent",
        "Direction",
        "Size",
        "EnteredAt",
        "ExitedAt",
        "EntryPrice",
        "ExitPrice",
        "Notes",
        "MatchStatus",
        "CreatedAt",
        "UpdatedAt",
    ],
    JOURNAL_ADJUSTMENTS_CSV: [
        "adjustment_id",
        "journal_id",
        "AdjustmentType",
        "Qty",
        "Price",
        "At",
        "Note",
        "CreatedAt",
        "UpdatedAt",
    ],
    JOURNAL_MATCHES_CSV: [
        "match_id",
        "journal_id",
        "trade_id",
        "TradeDay",
        "MatchType",
        "Score",
        "IsPrimary",
        "Status",
        "CreatedAt",
        "UpdatedAt",
    ],
    TAXONOMY_CSV: ["Domain", "Field", "Value", "Hint", "SortOrder", "Enabled"],
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

REQUIRED_TAXONOMY: dict[str, list[str]] = {
    "trade": ["Phase", "Context", "Setup", "SignalBar", "TradeIntent"],
    "day_plan": ["Bias", "ExpectedDayType"],
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


def validate_unified_taxonomy_or_raise() -> None:
    path = Path(TAXONOMY_CSV)
    if not path.exists():
        raise RuntimeError(f"taxonomy file is missing: {path}")

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise RuntimeError(f"failed to read taxonomy file {path}: {exc}") from exc

    required_cols = {"Domain", "Field", "Value", "Enabled"}
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise RuntimeError(f"taxonomy file missing required columns {missing_cols}: {path}")

    out = df.copy()
    out["Domain"] = out["Domain"].fillna("").astype(str).str.strip().str.lower()
    out["Field"] = out["Field"].fillna("").astype(str).str.strip()
    out["Value"] = out["Value"].fillna("").astype(str).str.strip()
    out["Enabled"] = out["Enabled"].astype(str).str.strip().str.lower().isin(["1", "true", "yes", "y"])
    out = out[(out["Value"] != "") & out["Enabled"]].copy()

    missing_groups: list[str] = []
    for domain, fields in REQUIRED_TAXONOMY.items():
        domain_df = out[out["Domain"] == domain]
        for field in fields:
            if domain_df[domain_df["Field"] == field].empty:
                missing_groups.append(f"{domain}.{field}")

    if missing_groups:
        raise RuntimeError(
            "taxonomy validation failed; missing enabled values for required groups: "
            + ", ".join(missing_groups)
        )
