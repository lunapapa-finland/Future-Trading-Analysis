from __future__ import annotations

import csv
import hashlib
import logging
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Dict, Any, List
from uuid import uuid4

from dashboard.config.env import BASE_DIR

PORTFOLIO_DIR = BASE_DIR / "data" / "portfolio"
PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
PORTFOLIO_CSV = PORTFOLIO_DIR / "equity.csv"  # legacy path, no longer used as source of truth
CASHFLOW_CSV = PORTFOLIO_DIR / "cashflow.csv"
TRADE_SUM_CSV = PORTFOLIO_DIR / "trade_sum.csv"

CASHFLOW_HEADERS = ["event_id", "date", "amount", "reason", "created_at"]
TRADE_SUM_HEADERS = ["date", "trade_pnl", "updated_at"]
log = logging.getLogger(__name__)


def _init_if_missing() -> None:
    if not CASHFLOW_CSV.exists():
        with CASHFLOW_CSV.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CASHFLOW_HEADERS)
            writer.writeheader()
    if not TRADE_SUM_CSV.exists():
        with TRADE_SUM_CSV.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=TRADE_SUM_HEADERS)
            writer.writeheader()
    if CASHFLOW_CSV.exists():
        try:
            with CASHFLOW_CSV.open("r", newline="") as f:
                reader = csv.DictReader(f)
                raw_rows = [row for row in reader]
            normalized_rows: List[Dict[str, Any]] = []
            for row in raw_rows:
                try:
                    day = _normalize_iso_date(row.get("date"))
                except ValueError:
                    continue
                normalized_rows.append(
                    {
                        "event_id": str(row.get("event_id", "")).strip(),
                        "date": day,
                        "amount": _to_float(row.get("amount")),
                        "reason": str(row.get("reason", "")).strip() or "deposit",
                        "created_at": str(row.get("created_at", "")).strip(),
                    }
                )
            _write_cashflow_rows(_sort_cashflow_rows(normalized_rows))
        except Exception:
            # Never block portfolio reads/writes on best-effort ordering maintenance.
            pass


def _read_rows() -> List[Dict[str, Any]]:
    return equity_series()


def _normalize_iso_date(raw: object) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("date is required")
    return datetime.fromisoformat(value).date().isoformat()


def _to_float(raw: object) -> float:
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _read_cashflow_rows() -> List[Dict[str, Any]]:
    _init_if_missing()
    with CASHFLOW_CSV.open("r", newline="") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]
    out: List[Dict[str, Any]] = []
    for row in rows:
        try:
            day = _normalize_iso_date(row.get("date"))
        except ValueError:
            continue
        out.append(
            {
                "event_id": str(row.get("event_id", "")).strip(),
                "date": day,
                "amount": _to_float(row.get("amount")),
                "reason": str(row.get("reason", "")).strip() or "deposit",
                "created_at": str(row.get("created_at", "")).strip(),
            }
        )
    return out


def _write_cashflow_rows(rows: List[Dict[str, Any]]) -> None:
    with CASHFLOW_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CASHFLOW_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "event_id": str(row.get("event_id", "")).strip(),
                    "date": str(row.get("date", "")).strip(),
                    "amount": f"{_to_float(row.get('amount')):.2f}",
                    "reason": str(row.get("reason", "")).strip() or "deposit",
                    "created_at": str(row.get("created_at", "")).strip(),
                }
            )


def _sort_cashflow_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            str(r.get("date", "")),
            str(r.get("created_at", "")),
            str(r.get("event_id", "")),
        ),
    )


def _read_trade_sum_rows() -> List[Dict[str, Any]]:
    _init_if_missing()
    with TRADE_SUM_CSV.open("r", newline="") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]
    out: List[Dict[str, Any]] = []
    for row in rows:
        try:
            day = _normalize_iso_date(row.get("date"))
        except ValueError:
            continue
        out.append(
            {
                "date": day,
                "trade_pnl": _to_float(row.get("trade_pnl")),
                "updated_at": str(row.get("updated_at", "")).strip(),
            }
        )
    return out


def _write_trade_sum_rows(rows: List[Dict[str, Any]]) -> None:
    with TRADE_SUM_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRADE_SUM_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "date": row["date"],
                    "trade_pnl": f"{float(row.get('trade_pnl', 0.0)):.2f}",
                    "updated_at": row.get("updated_at", ""),
                }
            )


def _append_cashflow_row(*, day: str, amount: float, reason: str) -> Dict[str, Any]:
    _init_if_missing()
    created_at = datetime.now(tz=timezone.utc).isoformat()
    entropy = f"{day}|{reason}|{amount:.2f}|{created_at}|{uuid4().hex}"
    event_id = hashlib.sha1(entropy.encode("utf-8")).hexdigest()[:16]
    row = {
        "event_id": event_id,
        "date": day,
        "amount": f"{amount:.2f}",
        "reason": reason,
        "created_at": created_at,
    }
    rows = _read_cashflow_rows()
    rows.append(
        {
            "event_id": row["event_id"],
            "date": row["date"],
            "amount": _to_float(row["amount"]),
            "reason": row["reason"],
            "created_at": row["created_at"],
        }
    )
    _write_cashflow_rows(_sort_cashflow_rows(rows))
    return row


def sync_trade_sum_from_performance_rows(rows: List[Dict[str, Any]], affected_dates: set[str]) -> None:
    """
    Incrementally update daily trade sums for affected dates only.
    `rows` must contain at least TradeDay and PnL(Net)-compatible keys.
    """
    if not affected_dates:
        return
    normalized_dates: set[str] = set()
    for d in affected_dates:
        try:
            normalized_dates.add(_normalize_iso_date(d))
        except ValueError:
            continue
    if not normalized_dates:
        return

    recomputed: Dict[str, float] = {}
    for row in rows:
        raw_day = row.get("TradeDay")
        if raw_day is None:
            continue
        try:
            day = _normalize_iso_date(raw_day)
        except ValueError:
            continue
        if day not in normalized_dates:
            continue
        pnl = _to_float(row.get("PnL(Net)", row.get("PnL", 0)))
        recomputed[day] = recomputed.get(day, 0.0) + pnl

    existing = _read_trade_sum_rows()
    kept = [row for row in existing if row["date"] not in normalized_dates]
    updated_at = datetime.now(tz=timezone.utc).isoformat()
    for day in sorted(recomputed.keys()):
        pnl = recomputed[day]
        if abs(pnl) < 1e-12:
            continue
        kept.append({"date": day, "trade_pnl": pnl, "updated_at": updated_at})
    kept.sort(key=lambda row: row["date"])
    _write_trade_sum_rows(kept)


def latest_equity() -> Dict[str, Any]:
    rows = equity_series()
    return rows[-1] if rows else {"date": "", "equity": 0.0, "pnl": 0.0, "reason": "none", "source": "none"}


def equity_series(limit: int | None = None) -> List[Dict[str, Any]]:
    trade_rows = _read_trade_sum_rows()
    cashflows = _read_cashflow_rows()

    trade_map: Dict[str, float] = {}
    for row in trade_rows:
        day = row["date"]
        trade_map[day] = trade_map.get(day, 0.0) + _to_float(row.get("trade_pnl"))

    cashflow_by_day: Dict[str, List[Dict[str, Any]]] = {}
    for row in cashflows:
        cashflow_by_day.setdefault(row["date"], []).append(row)
    for day in cashflow_by_day:
        cashflow_by_day[day].sort(key=lambda r: (str(r.get("created_at", "")), str(r.get("event_id", ""))))

    all_days = sorted(set(trade_map.keys()) | set(cashflow_by_day.keys()))
    running = 0.0
    rows: List[Dict[str, Any]] = []
    for day in all_days:
        trade_pnl = _to_float(trade_map.get(day, 0.0))
        if abs(trade_pnl) > 1e-12:
            running += trade_pnl
            rows.append(
                {
                    "date": day,
                    "equity": round(running, 2),
                    "pnl": round(trade_pnl, 2),
                    "reason": "trading",
                    "source": "trade_sum",
                }
            )
        for cash in cashflow_by_day.get(day, []):
            amount = _to_float(cash.get("amount"))
            running += amount
            rows.append(
                {
                    "date": day,
                    "equity": round(running, 2),
                    "pnl": round(amount, 2),
                    "reason": cash.get("reason", "deposit"),
                    "event_id": cash.get("event_id", ""),
                    "source": "cashflow",
                }
            )

    if limit is not None:
        return rows[-limit:]
    return rows


def append_daily_equity(trade_date: date, pnl: float) -> None:
    """
    Legacy compatibility helper: update one trade day in trade_sum.csv.
    """
    sync_trade_sum_from_performance_rows(
        [{"TradeDay": trade_date.isoformat(), "PnL(Net)": float(pnl)}],
        {trade_date.isoformat()},
    )


def append_manual(reason: str, amount: float, ts: datetime | None = None, date_override: str | None = None) -> Dict[str, Any]:
    """
    Append a manual adjustment as an immutable cashflow event.
    amount can be positive (deposit) or negative (withdraw).
    """
    ts = ts or datetime.now(tz=timezone.utc)
    if reason not in {"deposit", "withdraw"}:
        raise ValueError("reason must be deposit or withdraw")
    if date_override:
        ts = datetime.fromisoformat(date_override)
    day = ts.date().isoformat()
    if reason == "withdraw":
        amount = -abs(float(amount))
    else:
        amount = abs(float(amount))
    row = _append_cashflow_row(day=day, amount=amount, reason=reason)
    latest = latest_equity()
    return {
        "event_id": row["event_id"],
        "date": day,
        "pnl": float(row["amount"]),
        "reason": reason,
        "source": "cashflow",
        "equity": float(latest.get("equity", 0.0)),
    }
