from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Dict, Any, List

from dashboard.config.analysis import INITIAL_NET_LIQ, PORTFOLIO_START_DATE, RISK_FREE_RATE
from dashboard.config.env import BASE_DIR

PORTFOLIO_CSV = BASE_DIR / "data" / "portfolio" / "equity.csv"
PORTFOLIO_CSV.parent.mkdir(parents=True, exist_ok=True)

CSV_HEADERS = ["date", "equity", "pnl", "reason"]
log = logging.getLogger(__name__)


def _init_if_missing() -> None:
    if not PORTFOLIO_CSV.exists():
        with PORTFOLIO_CSV.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerow({"date": PORTFOLIO_START_DATE, "equity": f"{INITIAL_NET_LIQ:.2f}", "pnl": "0.00", "reason": "init"})


def _read_rows() -> List[Dict[str, Any]]:
    _init_if_missing()
    with PORTFOLIO_CSV.open("r", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def _write_rows(rows: List[Dict[str, Any]]) -> None:
    with PORTFOLIO_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _recalculate_equity(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        raw_date = str(row.get("date", "")).strip()
        if not raw_date:
            continue
        try:
            parsed_date = datetime.fromisoformat(raw_date).date().isoformat()
        except ValueError:
            continue
        try:
            pnl = float(row.get("pnl", 0) or 0)
        except (TypeError, ValueError):
            pnl = 0.0
        reason = str(row.get("reason", "")).strip() or "trading"
        # Keep the last event for a date.
        normalized[parsed_date] = {"date": parsed_date, "pnl": pnl, "reason": reason}

    ordered = sorted(normalized.values(), key=lambda r: r["date"])
    running = float(INITIAL_NET_LIQ)
    out: List[Dict[str, Any]] = []
    for row in ordered:
        running += float(row["pnl"])
        out.append(
            {
                "date": row["date"],
                "equity": f"{running:.2f}",
                "pnl": f"{float(row['pnl']):.2f}",
                "reason": row["reason"],
            }
        )
    return out


def _upsert_event(event_date: date, pnl: float, reason: str) -> List[Dict[str, Any]]:
    rows = _read_rows()
    target = event_date.isoformat()
    new_row = {"date": target, "equity": "0.00", "pnl": f"{float(pnl):.2f}", "reason": reason}
    replaced = False
    for i, row in enumerate(rows):
        if str(row.get("date", "")).strip() == target:
            rows[i] = new_row
            replaced = True
            break
    if not replaced:
        rows.append(new_row)
    recalculated = _recalculate_equity(rows)
    _write_rows(recalculated)
    return recalculated


def latest_equity() -> Dict[str, Any]:
    rows = _read_rows()
    return rows[-1] if rows else {"date": "1970-01-01", "equity": f"{INITIAL_NET_LIQ:.2f}", "pnl": "0.00", "reason": "init"}


def equity_series(limit: int | None = None) -> List[Dict[str, Any]]:
    rows = _read_rows()
    if limit is not None:
        return rows[-limit:]
    return rows


def append_daily_equity(trade_date: date, pnl: float) -> None:
    """
    Append a daily equity point using only the pnl for that day and previous equity.
    """
    _upsert_event(event_date=trade_date, pnl=pnl, reason="trading")


def append_manual(reason: str, amount: float, ts: datetime | None = None, date_override: str | None = None) -> Dict[str, Any]:
    """
    Append a manual adjustment (deposit/withdraw). amount can be positive (deposit) or negative (withdraw).
    date_override: optional ISO date string (YYYY-MM-DD) to use instead of now().
    """
    ts = ts or datetime.now(tz=timezone.utc)
    if date_override:
        try:
            ts = datetime.fromisoformat(date_override)
        except ValueError:
            log.warning("Invalid date_override '%s'; using current timestamp instead", date_override)
    rows = _upsert_event(event_date=ts.date(), pnl=amount, reason=reason)
    target = ts.date().isoformat()
    for row in rows:
        if row.get("date") == target:
            return row
    return rows[-1]
