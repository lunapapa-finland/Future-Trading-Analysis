from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd


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

    # Deterministic row id generation (non-security use).
    computed = out.apply(
        lambda row: hashlib.sha1(
            _trade_key_payload(row).encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:16],
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

