from __future__ import annotations

import csv
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Dict, Any, List

from dashboard.config.analysis import INITIAL_NET_LIQ, PORTFOLIO_START_DATE, RISK_FREE_RATE
from dashboard.config.env import BASE_DIR

PORTFOLIO_CSV = BASE_DIR / "data" / "portfolio" / "equity.csv"
PORTFOLIO_CSV.parent.mkdir(parents=True, exist_ok=True)

CSV_HEADERS = ["date", "equity", "pnl", "reason"]


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
    rows = _read_rows()
    # Ensure rows are sorted by date
    rows = sorted(rows, key=lambda r: r.get("date", ""))
    last_equity = float(rows[-1].get("equity", INITIAL_NET_LIQ)) if rows else INITIAL_NET_LIQ
    new_equity = last_equity + pnl
    updated_row = {"date": trade_date.isoformat(), "equity": f"{new_equity:.2f}", "pnl": f"{pnl:.2f}", "reason": "trading"}

    # Replace existing entry for the same date, otherwise append
    replaced = False
    for i, r in enumerate(rows):
        if r.get("date") == trade_date.isoformat():
            rows[i] = updated_row
            replaced = True
            break
    if not replaced:
        rows.append(updated_row)
    rows = sorted(rows, key=lambda r: r.get("date", ""))
    _write_rows(rows)


def append_manual(reason: str, amount: float, ts: datetime | None = None, date_override: str | None = None) -> Dict[str, Any]:
    """
    Append a manual adjustment (deposit/withdraw). amount can be positive (deposit) or negative (withdraw).
    date_override: optional ISO date string (YYYY-MM-DD) to use instead of now().
    """
    rows = _read_rows()
    rows = sorted(rows, key=lambda r: r.get("date", ""))
    last = rows[-1] if rows else {"equity": f"{INITIAL_NET_LIQ:.2f}"}
    prev_equity = float(last.get("equity", INITIAL_NET_LIQ))
    ts = ts or datetime.now(tz=timezone.utc)
    if date_override:
        try:
            ts = datetime.fromisoformat(date_override)
        except Exception:
            pass
    new_equity = prev_equity + amount
    new_row = {
        "date": ts.date().isoformat(),
        "equity": f"{new_equity:.2f}",
        "pnl": f"{amount:.2f}",
        "reason": reason,
    }
    # replace same-date entry if exists
    replaced = False
    for i, r in enumerate(rows):
        if r.get("date") == new_row["date"]:
            rows[i] = new_row
            replaced = True
            break
    if not replaced:
        rows.append(new_row)
    rows = sorted(rows, key=lambda r: r.get("date", ""))
    _write_rows(rows)
    return rows[-1]
