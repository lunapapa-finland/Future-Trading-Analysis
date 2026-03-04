from __future__ import annotations

from typing import Optional

import pandas as pd

from dashboard.config.settings import TRADE_JOURNAL_CSV, TRADE_JOURNAL_METADATA_CSV

KEY_COLUMNS = ["TradeDay", "ContractName", "IntradayIndex"]
TRADE_ID_COLUMN = "trade_id"
JOURNAL_COLUMNS = [TRADE_ID_COLUMN] + KEY_COLUMNS + ["Phase", "Context", "Setup", "SignalBar", "Comments"]
JOURNAL_FIELD_COLUMNS = ["Phase", "Context", "Setup", "SignalBar", "Comments"]


def _normalize_trade_day(value: object) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return str(value).strip()
    return ts.strftime("%Y-%m-%d")


def _empty_journal_df() -> pd.DataFrame:
    return pd.DataFrame(columns=JOURNAL_COLUMNS)


def _normalize_key_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if TRADE_ID_COLUMN not in out.columns:
        out[TRADE_ID_COLUMN] = ""
    out[TRADE_ID_COLUMN] = out[TRADE_ID_COLUMN].fillna("").astype(str).str.strip()
    for col in KEY_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out["TradeDay"] = out["TradeDay"].map(_normalize_trade_day)
    out["ContractName"] = out["ContractName"].astype(str).str.strip()
    out["IntradayIndex"] = pd.to_numeric(out["IntradayIndex"], errors="coerce").fillna(-1).astype(int).astype(str)
    return out


def effective_key(df: pd.DataFrame) -> pd.Series:
    out = _normalize_key_columns(df)
    legacy = (
        out["TradeDay"].astype(str).str.strip()
        + "|"
        + out["ContractName"].astype(str).str.strip()
        + "|"
        + out["IntradayIndex"].astype(str).str.strip()
    )
    tid = out[TRADE_ID_COLUMN].astype(str).str.strip()
    return tid.where(tid != "", legacy)


# Backward-compatible alias for internal callers.
_effective_key = effective_key


def build_journal_scaffold(performance_df: pd.DataFrame) -> pd.DataFrame:
    if performance_df.empty:
        return _empty_journal_df()
    src = _normalize_key_columns(performance_df)
    scaffold = src[[TRADE_ID_COLUMN] + KEY_COLUMNS].drop_duplicates(keep="last").copy()
    scaffold["Phase"] = ""
    scaffold["Context"] = ""
    scaffold["Setup"] = ""
    scaffold["SignalBar"] = ""
    scaffold["Comments"] = ""
    return scaffold[JOURNAL_COLUMNS]


def load_trade_journal(path: Optional[str] = None) -> pd.DataFrame:
    journal_path = path or TRADE_JOURNAL_CSV
    try:
        df = pd.read_csv(journal_path)
    except FileNotFoundError:
        return _empty_journal_df()
    except Exception:
        return _empty_journal_df()

    out = df.copy()
    for col in JOURNAL_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out = _normalize_key_columns(out)
    for col in JOURNAL_FIELD_COLUMNS:
        out[col] = out[col].fillna("").astype(str).str.strip()
    return out[JOURNAL_COLUMNS]


def sync_trade_journal(performance_df: pd.DataFrame, path: Optional[str] = None) -> pd.DataFrame:
    journal_path = path or TRADE_JOURNAL_CSV
    existing = load_trade_journal(journal_path)
    scaffold = build_journal_scaffold(performance_df)
    if scaffold.empty and existing.empty:
        existing.to_csv(journal_path, index=False)
        return existing

    if existing.empty:
        final_df = scaffold.copy()
    elif scaffold.empty:
        final_df = existing.copy()
    else:
        scaffold = scaffold.copy()
        existing = existing.copy()
        scaffold["__effective_key"] = effective_key(scaffold)
        existing["__effective_key"] = effective_key(existing)
        merged = scaffold.merge(existing, on="__effective_key", how="left", suffixes=("", "__existing"))
        # Keep current scaffold identity, fallback to existing identity when missing.
        for col in [TRADE_ID_COLUMN] + KEY_COLUMNS:
            existing_col = f"{col}__existing"
            if existing_col in merged.columns:
                merged[col] = merged[col].where(merged[col].astype(str).str.strip() != "", merged[existing_col])
                merged.drop(columns=[existing_col], inplace=True)
        for col in JOURNAL_FIELD_COLUMNS:
            merged[col] = merged[f"{col}__existing"].fillna(merged[col]).astype(str).str.strip()
            merged.drop(columns=[f"{col}__existing"], inplace=True)
        final_df = merged[JOURNAL_COLUMNS + ["__effective_key"]]

        # Include legacy journal rows not in current scaffold (do not lose user notes).
        carry = existing.merge(scaffold[["__effective_key"]], on="__effective_key", how="left", indicator=True)
        carry = carry[carry["_merge"] == "left_only"].drop(columns=["_merge"])
        if not carry.empty:
            final_df = pd.concat([final_df, carry[JOURNAL_COLUMNS + ["__effective_key"]]], ignore_index=True)

    final_df = _normalize_key_columns(final_df)
    final_df["__effective_key"] = effective_key(final_df)
    final_df = (
        final_df.drop_duplicates(subset=["__effective_key"], keep="last")
        .drop(columns=["__effective_key"])
        .sort_values(KEY_COLUMNS)
        .reset_index(drop=True)
    )
    final_df.to_csv(journal_path, index=False)
    return final_df


def load_trade_journal_metadata(path: Optional[str] = None) -> pd.DataFrame:
    meta_path = path or TRADE_JOURNAL_METADATA_CSV
    columns = ["Phase", "Context", "Setup", "SignalBar", "Validity", "RuleNote"]
    try:
        meta = pd.read_csv(meta_path)
    except FileNotFoundError:
        return pd.DataFrame(columns=columns)
    except Exception:
        return pd.DataFrame(columns=columns)

    out = meta.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = ""
    for col in columns:
        out[col] = out[col].fillna("").astype(str).str.strip()
    return out[columns]


def merge_trade_journal(df: pd.DataFrame, journal_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out

    base = _normalize_key_columns(out)
    journal = journal_df.copy() if journal_df is not None else load_trade_journal()
    if journal.empty:
        return out
    journal = _normalize_key_columns(journal)
    for col in JOURNAL_FIELD_COLUMNS:
        if col not in journal.columns:
            journal[col] = ""
        journal[col] = journal[col].fillna("").astype(str).str.strip()
    base["__effective_key"] = effective_key(base)
    journal["__effective_key"] = effective_key(journal)
    journal = journal[[TRADE_ID_COLUMN] + KEY_COLUMNS + JOURNAL_FIELD_COLUMNS + ["__effective_key"]].drop_duplicates(
        subset=["__effective_key"], keep="last"
    )

    merged = base.merge(journal, on="__effective_key", how="left", suffixes=("", "__journal"))
    # Keep base identity fields and fill missing trade_id from journal when available.
    if TRADE_ID_COLUMN in out.columns:
        journal_tid = merged[f"{TRADE_ID_COLUMN}__journal"] if f"{TRADE_ID_COLUMN}__journal" in merged.columns else pd.Series("", index=merged.index)
        out[TRADE_ID_COLUMN] = (
            out[TRADE_ID_COLUMN].fillna("").astype(str).str.strip().where(
                out[TRADE_ID_COLUMN].fillna("").astype(str).str.strip() != "",
                journal_tid.fillna("").astype(str).str.strip(),
            )
        )
    elif f"{TRADE_ID_COLUMN}__journal" in merged.columns:
        out[TRADE_ID_COLUMN] = merged[f"{TRADE_ID_COLUMN}__journal"].fillna("").astype(str).str.strip()
    for col in JOURNAL_FIELD_COLUMNS:
        # If the base dataframe already had this column, pandas keeps it as `col`
        # and writes journal values into `col__journal`.
        journal_col = f"{col}__journal" if f"{col}__journal" in merged.columns else col
        if col in out.columns:
            existing = out[col].fillna("").astype(str).str.strip()
            journal_vals = merged[journal_col].fillna("").astype(str).str.strip()
            out[col] = journal_vals.where(journal_vals != "", existing)
        else:
            out[col] = merged[journal_col].fillna("").astype(str).str.strip()
    return out


def _allowed_values(metadata_df: pd.DataFrame) -> dict[str, set[str]]:
    allowed = {"Phase": set(), "Context": set(), "Setup": set(), "SignalBar": set()}
    if metadata_df.empty:
        return allowed
    active = metadata_df[metadata_df["Validity"].isin(["allowed", "preferred"])]
    for col in allowed:
        values = set(v for v in active[col].astype(str).str.strip().tolist() if v and v != "*")
        allowed[col] = values
    return allowed


def _row_matches_rule(row: pd.Series, rule: pd.Series) -> bool:
    for col in ["Phase", "Context", "Setup", "SignalBar"]:
        rule_val = str(rule.get(col, "")).strip()
        row_val = str(row.get(col, "")).strip()
        if rule_val == "*":
            continue
        if row_val != rule_val:
            return False
    return True


def validate_trade_journal(
    journal_df: pd.DataFrame, metadata_df: Optional[pd.DataFrame] = None
) -> dict[str, pd.DataFrame | dict[str, int]]:
    journal = load_trade_journal() if journal_df is None else journal_df.copy()
    journal = _normalize_key_columns(journal)
    for col in JOURNAL_FIELD_COLUMNS:
        if col not in journal.columns:
            journal[col] = ""
        journal[col] = journal[col].fillna("").astype(str).str.strip()
    journal = journal[JOURNAL_COLUMNS]

    metadata = metadata_df.copy() if metadata_df is not None else load_trade_journal_metadata()
    allowed = _allowed_values(metadata)

    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    allowed_rules = metadata[metadata["Validity"].isin(["allowed", "preferred"])] if not metadata.empty else pd.DataFrame()
    preferred_rules = metadata[metadata["Validity"] == "preferred"] if not metadata.empty else pd.DataFrame()

    for _, row in journal.iterrows():
        key = {TRADE_ID_COLUMN: row.get(TRADE_ID_COLUMN, ""), **{k: row[k] for k in KEY_COLUMNS}}
        row_errors = []
        for field in ["Phase", "Context", "Setup", "SignalBar"]:
            val = str(row.get(field, "")).strip()
            if not val:
                row_errors.append(f"{field}:missing")
                continue
            if allowed[field] and val not in allowed[field]:
                row_errors.append(f"{field}:invalid_value({val})")
        if row_errors:
            violations.append({**key, "Issue": "; ".join(row_errors)})
            continue

        if not allowed_rules.empty:
            has_match = any(_row_matches_rule(row, rule) for _, rule in allowed_rules.iterrows())
            if not has_match:
                violations.append({**key, "Issue": "invalid_combination"})
                continue

        if not preferred_rules.empty:
            has_preferred = any(_row_matches_rule(row, rule) for _, rule in preferred_rules.iterrows())
            if not has_preferred:
                warnings.append({**key, "Issue": "no_preferred_combination_match"})

    key_cols = [TRADE_ID_COLUMN] + KEY_COLUMNS
    violations_df = pd.DataFrame(violations, columns=key_cols + ["Issue"])
    warnings_df = pd.DataFrame(warnings, columns=key_cols + ["Issue"])
    summary = {
        "RowsChecked": int(len(journal)),
        "Violations": int(len(violations_df)),
        "Warnings": int(len(warnings_df)),
    }
    return {"summary": summary, "violations": violations_df, "warnings": warnings_df}
