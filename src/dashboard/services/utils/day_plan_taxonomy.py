from __future__ import annotations

from typing import Any

import pandas as pd

from dashboard.config.settings import DAY_PLAN_TAXONOMY_CSV

TAXONOMY_COLUMNS = ["Field", "Value", "Hint", "SortOrder", "Enabled"]
FIELDS = ["Bias", "ExpectedDayType"]
DEFAULT_DAY_TYPES = [
    "Trend day",
    "TR day",
    "Trend from open",
    "Spike and channel",
    "Double distribution",
]
DEFAULT_BIAS = ["Bullish", "Bearish", "Neutral"]


def _empty_taxonomy_df() -> pd.DataFrame:
    return pd.DataFrame(columns=TAXONOMY_COLUMNS)


def load_day_plan_taxonomy(path: str | None = None) -> pd.DataFrame:
    target = path or DAY_PLAN_TAXONOMY_CSV
    try:
        df = pd.read_csv(target)
    except FileNotFoundError:
        return _empty_taxonomy_df()
    except Exception:
        return _empty_taxonomy_df()

    out = df.copy()
    for col in TAXONOMY_COLUMNS:
        if col not in out.columns:
            out[col] = "" if col != "Enabled" else True
    out["Field"] = out["Field"].astype(str).str.strip()
    out["Value"] = out["Value"].astype(str).str.strip()
    out["Hint"] = out["Hint"].fillna("").astype(str).str.strip()
    out["SortOrder"] = pd.to_numeric(out["SortOrder"], errors="coerce").fillna(9999).astype(int)
    out["Enabled"] = out["Enabled"].astype(str).str.strip().str.lower().isin(["1", "true", "yes", "y"])
    out = out[out["Field"].isin(FIELDS) & (out["Value"] != "")].copy()
    out = out.sort_values(["Field", "SortOrder", "Value"], kind="stable").reset_index(drop=True)
    return out[TAXONOMY_COLUMNS]


def day_plan_taxonomy_payload() -> dict[str, Any]:
    taxonomy = load_day_plan_taxonomy()

    by_field: dict[str, list[dict[str, Any]]] = {f: [] for f in FIELDS}
    for _, row in taxonomy.iterrows():
        if not bool(row["Enabled"]):
            continue
        by_field[str(row["Field"])].append(
            {
                "value": str(row["Value"]),
                "hint": str(row["Hint"] or ""),
                "order": int(row["SortOrder"]),
            }
        )

    for f in FIELDS:
        by_field[f] = sorted(by_field[f], key=lambda x: (x["order"], x["value"]))

    if not by_field["ExpectedDayType"]:
        by_field["ExpectedDayType"] = [{"value": x, "hint": "", "order": i + 1} for i, x in enumerate(DEFAULT_DAY_TYPES)]
    if not by_field["Bias"]:
        by_field["Bias"] = [{"value": x, "hint": "", "order": i + 1} for i, x in enumerate(DEFAULT_BIAS)]

    return {
        "bias": by_field["Bias"],
        "expected_day_type": by_field["ExpectedDayType"],
        "actual_day_type": by_field["ExpectedDayType"],
    }
