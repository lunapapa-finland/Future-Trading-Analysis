from __future__ import annotations

from typing import Any

import pandas as pd

from dashboard.config.settings import TRADE_TAG_TAXONOMY_CSV

TAXONOMY_COLUMNS = ["Field", "Value", "Hint", "SortOrder", "Enabled"]
FIELDS = ["Phase", "Context", "Setup", "SignalBar"]


def _empty_taxonomy_df() -> pd.DataFrame:
    return pd.DataFrame(columns=TAXONOMY_COLUMNS)


def load_tag_taxonomy(path: str | None = None) -> pd.DataFrame:
    target = path or TRADE_TAG_TAXONOMY_CSV
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


def taxonomy_payload() -> dict[str, Any]:
    taxonomy = load_tag_taxonomy()

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

    return {
        "phase": by_field["Phase"],
        "context": by_field["Context"],
        "setup": by_field["Setup"],
        "signal_bar": by_field["SignalBar"],
    }
