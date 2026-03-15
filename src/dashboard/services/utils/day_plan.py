from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from dashboard.config.settings import DAY_PLAN_CSV
from dashboard.services.utils.persistence import advisory_file_lock, atomic_write_csv, append_audit_event

DAY_PLAN_COLUMNS = [
    "Date",
    "Bias",
    "ExpectedDayType",
    "ActualDayType",
    "KeyLevelsHTFContext",
    "PrimaryPlan",
    "AvoidancePlan",
    "UpdatedAt",
]


def _normalize_date(raw: object) -> str:
    s = str(raw or "").strip()
    if not s:
        raise ValueError("Date is required")
    day = pd.to_datetime(s, errors="raise").date()
    if day.weekday() >= 5:
        raise ValueError("Date must be a weekday (Mon-Fri)")
    return day.isoformat()


def _normalize_text(raw: object) -> str:
    return str(raw or "").strip()


def _ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in DAY_PLAN_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out = out[DAY_PLAN_COLUMNS].copy()
    out["Date"] = out["Date"].fillna("").astype(str).str.strip()
    for col in ["Bias", "ExpectedDayType", "ActualDayType", "KeyLevelsHTFContext", "PrimaryPlan", "AvoidancePlan", "UpdatedAt"]:
        out[col] = out[col].fillna("").astype(str).str.strip()
    out = out[out["Date"] != ""].copy()
    out = out.sort_values(["Date", "UpdatedAt"], kind="stable").drop_duplicates(subset=["Date"], keep="last").reset_index(drop=True)
    return out


def load_day_plan() -> pd.DataFrame:
    try:
        return _ensure_schema(pd.read_csv(DAY_PLAN_CSV))
    except FileNotFoundError:
        return pd.DataFrame(columns=DAY_PLAN_COLUMNS)
    except Exception:
        return pd.DataFrame(columns=DAY_PLAN_COLUMNS)


def list_day_plan(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    df = load_day_plan()
    if df.empty:
        return []
    if start:
        s = _normalize_date(start)
        df = df[df["Date"] >= s].copy()
    if end:
        e = _normalize_date(end)
        df = df[df["Date"] <= e].copy()
    return df.sort_values("Date", kind="stable").to_dict(orient="records")


def upsert_day_plan_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    if not isinstance(rows, list):
        raise ValueError("rows must be an array")
    updated = 0
    inserted = 0
    changed_dates: list[str] = []
    with advisory_file_lock(DAY_PLAN_CSV):
        existing = load_day_plan()
        by_date = {str(r.get("Date", "")): dict(r) for r in existing.to_dict(orient="records")}
        now = datetime.now(timezone.utc).isoformat()
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            day = _normalize_date(raw.get("Date"))
            next_row = {
                "Date": day,
                "Bias": _normalize_text(raw.get("Bias")),
                "ExpectedDayType": _normalize_text(raw.get("ExpectedDayType")),
                "ActualDayType": _normalize_text(raw.get("ActualDayType")),
                "KeyLevelsHTFContext": _normalize_text(raw.get("KeyLevelsHTFContext")),
                "PrimaryPlan": _normalize_text(raw.get("PrimaryPlan")),
                "AvoidancePlan": _normalize_text(raw.get("AvoidancePlan")),
                "UpdatedAt": now,
            }
            if day in by_date:
                updated += 1
            else:
                inserted += 1
            by_date[day] = next_row
            changed_dates.append(day)

        out = pd.DataFrame(list(by_date.values()), columns=DAY_PLAN_COLUMNS)
        out = _ensure_schema(out)
        atomic_write_csv(out, DAY_PLAN_CSV)

    append_audit_event(
        "day_plan_upserted",
        {
            "day_plan_csv": DAY_PLAN_CSV,
            "rows_requested": len(rows),
            "updated": updated,
            "inserted": inserted,
            "dates": sorted(set(changed_dates)),
        },
        actor="api:/day-plan",
    )
    return {"updated": updated, "inserted": inserted}
