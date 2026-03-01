from __future__ import annotations

import hashlib
from typing import Optional

import numpy as np
import pandas as pd

from dashboard.config.settings import TRADE_LABELS_CSV


def _norm_dt(value: object) -> str:
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.isoformat()


def _norm_num(value: object, decimals: int = 6) -> str:
    val = pd.to_numeric(value, errors="coerce")
    if pd.isna(val):
        return ""
    return f"{float(val):.{decimals}f}"


def _norm_str(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip().upper()


def _trade_key_payload(row: pd.Series) -> str:
    parts = [
        _norm_str(row.get("ContractName")),
        _norm_dt(row.get("EnteredAt")),
        _norm_dt(row.get("ExitedAt")),
        _norm_num(row.get("EntryPrice")),
        _norm_num(row.get("ExitPrice")),
        _norm_num(row.get("Size"), decimals=0),
        _norm_str(row.get("Type")),
    ]
    return "|".join(parts)


def ensure_trade_id(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        if "trade_id" not in out.columns:
            out["trade_id"] = pd.Series(dtype="object")
        return out

    missing_mask = (
        ("trade_id" not in out.columns)
        or out["trade_id"].isna().any()
        or (out["trade_id"].astype(str).str.strip() == "").any()
    )
    if not missing_mask:
        return out

    computed = out.apply(
        lambda row: hashlib.sha1(_trade_key_payload(row).encode("utf-8")).hexdigest()[:16],
        axis=1,
    )
    if "trade_id" in out.columns:
        existing_raw = out["trade_id"]
        existing = existing_raw.astype(str).str.strip()
        missing_existing = existing_raw.isna() | existing.isin(["", "nan", "None", "<NA>"])
        out["trade_id"] = np.where(missing_existing, computed, existing)
    else:
        out["trade_id"] = computed

    # Resolve rare hash collisions deterministically.
    dup_idx = out.groupby("trade_id", observed=True).cumcount()
    out["trade_id"] = np.where(dup_idx > 0, out["trade_id"] + "-" + dup_idx.astype(str), out["trade_id"])
    return out


def load_trade_labels(path: Optional[str] = None) -> pd.DataFrame:
    label_path = path or TRADE_LABELS_CSV
    try:
        labels = pd.read_csv(label_path)
    except FileNotFoundError:
        return pd.DataFrame(columns=["trade_id"])
    except Exception:
        return pd.DataFrame(columns=["trade_id"])

    if "trade_id" not in labels.columns:
        return pd.DataFrame(columns=["trade_id"])
    labels = labels.copy()
    labels["trade_id"] = labels["trade_id"].astype(str).str.strip()
    labels = labels[labels["trade_id"] != ""]
    if labels.empty:
        return pd.DataFrame(columns=["trade_id"])
    labels = labels.drop_duplicates(subset=["trade_id"], keep="last")
    return labels


def merge_trade_labels(df: pd.DataFrame, labels_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    out = ensure_trade_id(df)
    labels = labels_df.copy() if labels_df is not None else load_trade_labels()
    if labels.empty or "trade_id" not in labels.columns:
        return out

    labels = labels.copy()
    labels["trade_id"] = labels["trade_id"].astype(str).str.strip()
    label_cols = [c for c in labels.columns if c != "trade_id"]
    if not label_cols:
        return out

    merged = out.merge(labels, on="trade_id", how="left", suffixes=("", "__label"))
    for col in label_cols:
        label_col = f"{col}__label"
        if label_col in merged.columns and col in merged.columns:
            merged[col] = merged[label_col].combine_first(merged[col])
            merged.drop(columns=[label_col], inplace=True)
        elif label_col in merged.columns:
            merged[col] = merged[label_col]
            merged.drop(columns=[label_col], inplace=True)
        elif col in merged.columns:
            # Column came from labels and no base column existed; keep as-is.
            continue
        else:
            merged[col] = np.nan
    return merged
