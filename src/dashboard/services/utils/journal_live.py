from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any
import uuid

import pandas as pd

from dashboard.config.analysis import ANALYSIS_TIMEZONE
from dashboard.config.app_config import get_app_config
from dashboard.config.settings import JOURNAL_LIVE_CSV, JOURNAL_ADJUSTMENTS_CSV, JOURNAL_MATCHES_CSV, CONTRACT_SPECS_CSV, PERFORMANCE_CSV, DAY_PLAN_CSV
from dashboard.services.utils.persistence import advisory_file_lock, atomic_write_csv, append_audit_event
from dashboard.services.utils.trade_enrichment import ensure_trade_id

JOURNAL_COLUMNS = [
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
    "MaxLossUSD",
    "EnteredAt",
    "ExitedAt",
    "EntryPrice",
    "TakeProfitPrice",
    "StopLossPrice",
    "ExitPrice",
    "PotentialRiskUSD",
    "PotentialRewardUSD",
    "WinLossRatio",
    "RuleStatus",
    "Notes",
    "MatchStatus",
    "CreatedAt",
    "UpdatedAt",
]

ADJUSTMENT_COLUMNS = [
    "adjustment_id",
    "journal_id",
    "LegIndex",
    "Qty",
    "EntryPrice",
    "TakeProfitPrice",
    "StopLossPrice",
    "ExitPrice",
    "EnteredAt",
    "ExitedAt",
    "RiskUSD",
    "RewardUSD",
    "WinLossRatio",
    "Note",
    "CreatedAt",
    "UpdatedAt",
]

MATCH_COLUMNS = [
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
]

DIRECTION_VALUES = {"Long", "Short"}
TRADE_INTENT_KEYS = {"scalp", "swing", "scale_in"}
GROSS_PNL_TOLERANCE = 0.05
DEFAULT_DAILY_MAX_TRADE = 5
DEFAULT_DAILY_MAX_LOSS = 500.0


def _now_local_iso() -> str:
    return datetime.now(ZoneInfo(ANALYSIS_TIMEZONE)).isoformat()


def _normalize_trade_day(raw: object) -> str:
    s = str(raw or "").strip()
    if not s:
        raise ValueError("TradeDay is required")
    day = pd.to_datetime(s, errors="raise").date()
    if day.weekday() >= 5:
        raise ValueError("TradeDay must be a weekday (Mon-Fri)")
    return day.isoformat()


def _normalize_text(raw: object) -> str:
    return str(raw or "").strip()


def _normalize_opt_num(raw: object) -> str:
    if raw is None or str(raw).strip() == "":
        return ""
    val = pd.to_numeric(raw, errors="coerce")
    if pd.isna(val):
        raise ValueError(f"invalid numeric value: {raw}")
    return str(float(val))


def _normalize_size(raw: object) -> str:
    val = pd.to_numeric(raw, errors="coerce")
    if pd.isna(val):
        raise ValueError("Size is required and must be numeric")
    if float(val) <= 0:
        raise ValueError("Size must be positive")
    return str(float(val))


def _normalize_positive_num(raw: object, field: str) -> str:
    val = pd.to_numeric(raw, errors="coerce")
    if pd.isna(val):
        raise ValueError(f"{field} is required and must be numeric")
    f = float(val)
    if f <= 0:
        raise ValueError(f"{field} must be positive")
    return str(f)


def _intent_key(raw: object) -> str:
    s = _normalize_text(raw).lower().replace("-", "_").replace(" ", "_")
    if s not in TRADE_INTENT_KEYS:
        raise ValueError("TradeIntent must be one of: Scalp, Swing, Scale-in")
    return s


def _load_point_values() -> dict[str, float]:
    try:
        df = pd.read_csv(CONTRACT_SPECS_CSV)
    except Exception:
        return {}
    if "symbol" not in df.columns or "point_value" not in df.columns:
        return {}
    out: dict[str, float] = {}
    for _, row in df.iterrows():
        symbol = _normalize_text(row.get("symbol")).upper()
        pv = pd.to_numeric(row.get("point_value"), errors="coerce")
        if symbol and pd.notna(pv) and float(pv) > 0:
            out[symbol] = float(pv)
    return out


def _live_guardrails() -> tuple[int, float]:
    cfg = get_app_config()
    live_cfg = cfg.get("live_journal", {}) if isinstance(cfg, dict) else {}
    analysis_cfg = cfg.get("analysis", {}) if isinstance(cfg, dict) else {}
    rc_cfg = analysis_cfg.get("rule_compliance", {}) if isinstance(analysis_cfg, dict) else {}
    raw_trade = live_cfg.get("daily_max_trade", DEFAULT_DAILY_MAX_TRADE) if isinstance(live_cfg, dict) else DEFAULT_DAILY_MAX_TRADE
    raw_loss = (
        live_cfg.get("daily_max_loss", rc_cfg.get("max_daily_loss", DEFAULT_DAILY_MAX_LOSS))
        if isinstance(live_cfg, dict)
        else rc_cfg.get("max_daily_loss", DEFAULT_DAILY_MAX_LOSS)
    )
    max_trade = int(pd.to_numeric(raw_trade, errors="coerce")) if pd.notna(pd.to_numeric(raw_trade, errors="coerce")) else DEFAULT_DAILY_MAX_TRADE
    max_loss = float(pd.to_numeric(raw_loss, errors="coerce")) if pd.notna(pd.to_numeric(raw_loss, errors="coerce")) else DEFAULT_DAILY_MAX_LOSS
    if max_trade <= 0:
        max_trade = DEFAULT_DAILY_MAX_TRADE
    if max_loss <= 0:
        max_loss = DEFAULT_DAILY_MAX_LOSS
    return max_trade, max_loss


def _safe_float(raw: object) -> float | None:
    val = pd.to_numeric(raw, errors="coerce")
    if pd.isna(val):
        return None
    return float(val)


def _journal_row_realized_loss_usd(row: dict[str, Any], point_values: dict[str, float]) -> float:
    direction = _normalize_text(row.get("Direction")).title()
    if direction not in DIRECTION_VALUES:
        return 0.0
    contract = _normalize_text(row.get("ContractName")).upper()
    point_value = point_values.get(contract)
    if point_value is None or point_value <= 0:
        return 0.0
    adjustments = row.get("adjustments")
    if isinstance(adjustments, list) and adjustments:
        pnl_total = 0.0
        for a in adjustments:
            if not isinstance(a, dict):
                continue
            qty = _safe_float(a.get("Qty"))
            entry = _safe_float(a.get("EntryPrice"))
            exit_px = _safe_float(a.get("ExitPrice"))
            if qty is None or qty <= 0 or entry is None or exit_px is None:
                return 0.0
            leg = (exit_px - entry) * point_value * qty if direction == "Long" else (entry - exit_px) * point_value * qty
            pnl_total += leg
        return abs(pnl_total) if pnl_total < 0 else 0.0

    size = _safe_float(row.get("Size"))
    entry = _safe_float(row.get("EntryPrice"))
    exit_px = _safe_float(row.get("ExitPrice"))
    if size is None or size <= 0 or entry is None or exit_px is None:
        return 0.0
    pnl = (exit_px - entry) * point_value * size if direction == "Long" else (entry - exit_px) * point_value * size
    return abs(pnl) if pnl < 0 else 0.0


def live_daily_limit_status(
    rows: list[dict[str, Any]],
    *,
    point_values: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    max_trade, max_loss = _live_guardrails()
    pv = point_values if point_values is not None else _load_point_values()
    by_day: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        day = _normalize_text(row.get("TradeDay"))
        if not day:
            continue
        bucket = by_day.setdefault(
            day,
            {
                "TradeDay": day,
                "trade_count": 0,
                "cumulative_loss_usd": 0.0,
                "daily_max_trade": max_trade,
                "daily_max_loss": max_loss,
            },
        )
        bucket["trade_count"] += 1
        bucket["cumulative_loss_usd"] += _journal_row_realized_loss_usd(row, pv)

    out: list[dict[str, Any]] = []
    for day in sorted(by_day.keys()):
        row = by_day[day]
        trade_reached = int(row["trade_count"]) >= int(row["daily_max_trade"])
        loss_reached = float(row["cumulative_loss_usd"]) >= float(row["daily_max_loss"])
        row["max_trade_reached"] = trade_reached
        row["max_loss_reached"] = loss_reached
        row["blocked"] = trade_reached or loss_reached
        row["cumulative_loss_usd"] = round(float(row["cumulative_loss_usd"]), 6)
        out.append(row)
    return out


def _status_by_day(rows: list[dict[str, Any]], *, point_values: dict[str, float]) -> dict[str, dict[str, Any]]:
    return {str(r.get("TradeDay", "")): r for r in live_daily_limit_status(rows, point_values=point_values)}


def _day_plan_row(day: str) -> dict[str, Any] | None:
    try:
        df = pd.read_csv(DAY_PLAN_CSV)
    except Exception:
        return None
    if df.empty or "Date" not in df.columns:
        return None
    out = df.copy()
    out["Date"] = out["Date"].fillna("").astype(str).str.strip()
    hit = out[out["Date"] == day]
    if hit.empty:
        return None
    hit = hit.sort_values("Date", kind="stable")
    return hit.iloc[-1].to_dict()


def _require_pre_trade_plan_completed(day: str) -> None:
    row = _day_plan_row(day)
    required = ["Bias", "ExpectedDayType", "KeyLevelsHTFContext", "PrimaryPlan", "AvoidancePlan"]
    if not row:
        raise ValueError(
            f"pre-trade plan required for {day}: save Daily Sum first (Bias, ExpectedDayType, KeyLevelsHTFContext, PrimaryPlan, AvoidancePlan)"
        )
    missing = [k for k in required if _normalize_text(row.get(k, "")) == ""]
    if missing:
        raise ValueError(f"pre-trade plan incomplete for {day}: missing {', '.join(missing)}")


def _latest_row_for_day(rows_by_id: dict[str, dict[str, Any]], day: str) -> dict[str, Any] | None:
    day_rows = [r for r in rows_by_id.values() if _normalize_text(r.get("TradeDay")) == day]
    if not day_rows:
        return None
    day_rows.sort(
        key=lambda r: (
            int(pd.to_numeric(r.get("SeqInDay"), errors="coerce") or 0),
            _normalize_text(r.get("UpdatedAt")),
            _normalize_text(r.get("journal_id")),
        )
    )
    return day_rows[-1]


def _rows_with_adjustments(
    rows_by_id: dict[str, dict[str, Any]],
    adjustment_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_adj: dict[str, list[dict[str, Any]]] = {}
    for a in adjustment_rows:
        jid = _normalize_text(a.get("journal_id"))
        if not jid:
            continue
        by_adj.setdefault(jid, []).append(dict(a))
    out: list[dict[str, Any]] = []
    for jid, row in rows_by_id.items():
        next_row = dict(row)
        next_row["adjustments"] = by_adj.get(str(jid), [])
        out.append(next_row)
    return out


def _normalize_direction(raw: object) -> str:
    v = str(raw or "").strip().title()
    if v not in DIRECTION_VALUES:
        raise ValueError("Direction must be one of: Long, Short")
    return v


def _normalize_local_timestamp(raw: object, field: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"invalid {field}")
    if ts.tzinfo is None:
        ts = ts.tz_localize(ANALYSIS_TIMEZONE)
    else:
        ts = ts.tz_convert(ANALYSIS_TIMEZONE)
    return ts.isoformat()


def _ensure_journal_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in JOURNAL_COLUMNS:
        out[col] = out[col] if col in out.columns else ""
    out = out[JOURNAL_COLUMNS].copy()
    for col in JOURNAL_COLUMNS:
        out[col] = out[col].fillna("").astype(str).str.strip()
    if out.empty:
        return out
    out["SeqInDay"] = pd.to_numeric(out["SeqInDay"], errors="coerce").fillna(0).astype(int)
    out = out[out["journal_id"] != ""].copy()
    out = out.sort_values(["TradeDay", "SeqInDay", "UpdatedAt"], kind="stable")
    out = out.drop_duplicates(subset=["journal_id"], keep="last").reset_index(drop=True)
    return out


def _ensure_adjustment_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ADJUSTMENT_COLUMNS:
        out[col] = out[col] if col in out.columns else ""
    out = out[ADJUSTMENT_COLUMNS].copy()
    for col in ADJUSTMENT_COLUMNS:
        out[col] = out[col].fillna("").astype(str).str.strip()
    if out.empty:
        return out
    out["LegIndex"] = pd.to_numeric(out["LegIndex"], errors="coerce").fillna(0).astype(int)
    out = out[out["adjustment_id"] != ""].copy()
    out = out.sort_values(["journal_id", "LegIndex", "CreatedAt", "adjustment_id"], kind="stable")
    out = out.drop_duplicates(subset=["adjustment_id"], keep="last").reset_index(drop=True)
    return out


def _ensure_match_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in MATCH_COLUMNS:
        out[col] = out[col] if col in out.columns else ""
    out = out[MATCH_COLUMNS].copy()
    for col in MATCH_COLUMNS:
        out[col] = out[col].fillna("").astype(str).str.strip()
    if out.empty:
        return out
    out["IsPrimary"] = out["IsPrimary"].str.lower().isin(["1", "true", "yes", "y"]).map(lambda x: "true" if x else "false")
    out["Score"] = pd.to_numeric(out["Score"], errors="coerce").fillna(0.0).astype(float).map(lambda v: f"{v:.4f}")
    out = out[out["match_id"] != ""].copy()
    out = out.sort_values(["TradeDay", "CreatedAt", "match_id"], kind="stable")
    out = out.drop_duplicates(subset=["match_id"], keep="last").reset_index(drop=True)
    return out


def load_journal_live() -> pd.DataFrame:
    try:
        return _ensure_journal_schema(pd.read_csv(JOURNAL_LIVE_CSV))
    except FileNotFoundError:
        return pd.DataFrame(columns=JOURNAL_COLUMNS)
    except Exception:
        return pd.DataFrame(columns=JOURNAL_COLUMNS)


def load_journal_adjustments() -> pd.DataFrame:
    try:
        return _ensure_adjustment_schema(pd.read_csv(JOURNAL_ADJUSTMENTS_CSV))
    except FileNotFoundError:
        return pd.DataFrame(columns=ADJUSTMENT_COLUMNS)
    except Exception:
        return pd.DataFrame(columns=ADJUSTMENT_COLUMNS)


def load_journal_matches() -> pd.DataFrame:
    try:
        return _ensure_match_schema(pd.read_csv(JOURNAL_MATCHES_CSV))
    except FileNotFoundError:
        return pd.DataFrame(columns=MATCH_COLUMNS)
    except Exception:
        return pd.DataFrame(columns=MATCH_COLUMNS)


def _next_seq_for_day(df: pd.DataFrame, day: str) -> int:
    if df.empty:
        return 1
    day_rows = df[df["TradeDay"] == day]
    if day_rows.empty:
        return 1
    return int(pd.to_numeric(day_rows["SeqInDay"], errors="coerce").fillna(0).max()) + 1


def _normalize_adjustments(
    journal_id: str,
    adjustments: list[dict[str, Any]] | None,
    now_iso: str,
    *,
    direction: str,
    trade_intent: str,
    point_value: float,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    if not adjustments:
        raise ValueError("At least one execution detail row is required")
    intent = _intent_key(trade_intent)
    if intent in {"scalp", "swing"} and len(adjustments) != 1:
        raise ValueError(f"{trade_intent} requires exactly one execution detail row")
    if intent == "scale_in" and len(adjustments) < 1:
        raise ValueError("Scale-in requires at least one execution detail row")

    out: list[dict[str, str]] = []
    total_qty = 0.0
    total_risk = 0.0
    total_reward = 0.0
    weighted_entry = 0.0
    weighted_tp = 0.0
    weighted_sl = 0.0
    final_exits: list[float] = []
    final_exited_at: list[str] = []
    entered_at_values: list[pd.Timestamp] = []
    direction_key = direction.lower()

    for raw in adjustments:
        if not isinstance(raw, dict):
            continue
        adj_id = _normalize_text(raw.get("adjustment_id")) or f"adj_{uuid.uuid4().hex[:12]}"
        leg_index = int(pd.to_numeric(raw.get("LegIndex", len(out) + 1), errors="coerce")) if str(raw.get("LegIndex", "")).strip() else (len(out) + 1)
        qty = _normalize_positive_num(raw.get("Qty", raw.get("qty")), "Qty")
        entry = _normalize_positive_num(raw.get("EntryPrice", raw.get("entry_price")), "EntryPrice")
        tp = _normalize_positive_num(raw.get("TakeProfitPrice", raw.get("take_profit_price")), "TakeProfitPrice")
        sl = _normalize_positive_num(raw.get("StopLossPrice", raw.get("stop_loss_price")), "StopLossPrice")
        exit_price = _normalize_opt_num(raw.get("ExitPrice", raw.get("exit_price")))
        entered_at = _normalize_local_timestamp(raw.get("EnteredAt", raw.get("entered_at")), "EnteredAt")
        exited_at = _normalize_local_timestamp(raw.get("ExitedAt", raw.get("exited_at")), "ExitedAt")
        note = _normalize_text(raw.get("Note", raw.get("note", "")))
        q = float(qty)
        e = float(entry)
        t = float(tp)
        s = float(sl)
        if direction_key == "long":
            if not (s < e < t):
                raise ValueError("For Long, StopLossPrice < EntryPrice < TakeProfitPrice is required")
        else:
            if not (t < e < s):
                raise ValueError("For Short, TakeProfitPrice < EntryPrice < StopLossPrice is required")
        risk = abs(e - s) * point_value * q
        reward = abs(t - e) * point_value * q
        ratio = (reward / risk) if risk > 0 else 0.0
        total_qty += q
        total_risk += risk
        total_reward += reward
        weighted_entry += e * q
        weighted_tp += t * q
        weighted_sl += s * q
        if exit_price != "":
            final_exits.append(float(exit_price))
        if exited_at:
            final_exited_at.append(exited_at)
        if entered_at:
            ts = pd.to_datetime(entered_at, errors="coerce")
            if pd.notna(ts):
                entered_at_values.append(ts)

        row = {
            "adjustment_id": adj_id,
            "journal_id": journal_id,
            "LegIndex": str(max(1, leg_index)),
            "Qty": qty,
            "EntryPrice": entry,
            "TakeProfitPrice": tp,
            "StopLossPrice": sl,
            "ExitPrice": exit_price,
            "EnteredAt": entered_at,
            "ExitedAt": exited_at,
            "RiskUSD": f"{risk:.6f}",
            "RewardUSD": f"{reward:.6f}",
            "WinLossRatio": f"{ratio:.6f}",
            "Note": note,
            "CreatedAt": now_iso,
            "UpdatedAt": now_iso,
        }
        out.append(row)
    out.sort(key=lambda r: (int(pd.to_numeric(r.get("LegIndex"), errors="coerce") or 0), str(r.get("adjustment_id", ""))))
    if len({round(v, 10) for v in final_exits}) > 1:
        raise ValueError("Final exit only is supported: all ExitPrice values must be the same")
    if len(set(final_exited_at)) > 1:
        raise ValueError("Final exit only is supported: all ExitedAt values must be the same when provided")
    avg_entry = (weighted_entry / total_qty) if total_qty > 0 else 0.0
    avg_tp = (weighted_tp / total_qty) if total_qty > 0 else 0.0
    avg_sl = (weighted_sl / total_qty) if total_qty > 0 else 0.0
    summary = {
        "Size": str(total_qty),
        "EntryPrice": f"{avg_entry:.6f}" if total_qty > 0 else "",
        "TakeProfitPrice": f"{avg_tp:.6f}" if total_qty > 0 else "",
        "StopLossPrice": f"{avg_sl:.6f}" if total_qty > 0 else "",
        "ExitPrice": f"{final_exits[0]:.6f}" if final_exits else "",
        "EnteredAt": min(entered_at_values).isoformat() if entered_at_values else "",
        "ExitedAt": final_exited_at[0] if final_exited_at else "",
        "PotentialRiskUSD": f"{total_risk:.6f}",
        "PotentialRewardUSD": f"{total_reward:.6f}",
        "WinLossRatio": f"{(total_reward / total_risk):.6f}" if total_risk > 0 else "",
    }
    return out, summary


def list_live_journal(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    journal = load_journal_live()
    if journal.empty:
        return []
    if start:
        s = _normalize_trade_day(start)
        journal = journal[journal["TradeDay"] >= s].copy()
    if end:
        e = _normalize_trade_day(end)
        journal = journal[journal["TradeDay"] <= e].copy()

    adjustments = load_journal_adjustments()
    matches = load_journal_matches()
    if not matches.empty:
        matches = matches[matches["Status"] == "active"].copy()
    by_adj: dict[str, list[dict[str, Any]]] = {}
    for _, row in adjustments.iterrows():
        key = str(row["journal_id"])
        by_adj.setdefault(key, []).append(row.to_dict())
    by_match: dict[str, list[dict[str, Any]]] = {}
    for _, row in matches.iterrows():
        key = str(row["journal_id"])
        by_match.setdefault(key, []).append(row.to_dict())

    rows = []
    for _, row in journal.sort_values(["TradeDay", "SeqInDay"], kind="stable").iterrows():
        d = row.to_dict()
        jid = str(d.get("journal_id", ""))
        d["adjustments"] = by_adj.get(jid, [])
        d["matches"] = by_match.get(jid, [])
        rows.append(d)
    return rows


def list_active_matches(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    matches = load_journal_matches()
    if matches.empty:
        return []
    out = matches[matches["Status"] == "active"].copy()
    if start:
        s = pd.to_datetime(str(start), errors="coerce")
        if pd.notna(s):
            out = out[out["TradeDay"] >= s.date().isoformat()].copy()
    if end:
        e = pd.to_datetime(str(end), errors="coerce")
        if pd.notna(e):
            out = out[out["TradeDay"] <= e.date().isoformat()].copy()
    if out.empty:
        return []
    out = out.sort_values(["TradeDay", "CreatedAt", "match_id"], kind="stable")
    return out.to_dict(orient="records")


def delete_live_journal_row(journal_id: str, *, actor: str = "api:/journal/live/delete") -> dict[str, int]:
    j_id = _normalize_text(journal_id)
    if not j_id:
        raise ValueError("journal_id is required")
    now_iso = _now_local_iso()

    with advisory_file_lock(JOURNAL_MATCHES_CSV):
        matches = load_journal_matches()
        if not matches.empty:
            active = matches[
                (matches["journal_id"].astype(str) == j_id)
                & (matches["Status"].astype(str).str.strip().str.lower() == "active")
            ]
            if not active.empty:
                raise ValueError("journal has active match links; unlink first before delete")

    with advisory_file_lock(JOURNAL_LIVE_CSV):
        journal = load_journal_live()
        if journal.empty:
            raise ValueError("journal row not found")
        mask = journal["journal_id"].astype(str) == j_id
        if not mask.any():
            raise ValueError("journal row not found")
        status = _normalize_text(journal.loc[mask, "MatchStatus"].iloc[0]).lower() or "unmatched"
        if status not in {"initial", "unmatched", "needs_reconfirm"}:
            raise ValueError("journal delete is restricted to initial/unmatched or needs_reconfirm status")
        deleted = int(mask.sum())
        out_journal = journal.loc[~mask].copy()
        atomic_write_csv(_ensure_journal_schema(out_journal), JOURNAL_LIVE_CSV)

    deleted_adjustments = 0
    with advisory_file_lock(JOURNAL_ADJUSTMENTS_CSV):
        adjustments = load_journal_adjustments()
        if not adjustments.empty:
            amask = adjustments["journal_id"].astype(str) == j_id
            deleted_adjustments = int(amask.sum())
            out_adj = adjustments.loc[~amask].copy()
            atomic_write_csv(_ensure_adjustment_schema(out_adj), JOURNAL_ADJUSTMENTS_CSV)

    append_audit_event(
        "live_journal_deleted",
        {
            "journal_id": j_id,
            "deleted": deleted,
            "deleted_adjustments": deleted_adjustments,
        },
        actor=actor,
    )
    return {"deleted": deleted, "deleted_adjustments": deleted_adjustments}


def upsert_live_journal_rows(rows: list[dict[str, Any]], *, actor: str = "api:/journal/live") -> dict[str, int]:
    if not isinstance(rows, list):
        raise ValueError("rows must be an array")
    inserted = 0
    updated = 0
    changed_ids: list[str] = []
    now_iso = _now_local_iso()
    point_values = _load_point_values()

    with advisory_file_lock(JOURNAL_LIVE_CSV):
        journal = load_journal_live()
        adjustments_df = load_journal_adjustments()
        matches_df = load_journal_matches()
        by_id = {str(r.get("journal_id", "")): dict(r) for r in journal.to_dict(orient="records")}
        matches_list = matches_df.to_dict(orient="records")
        active_journal_ids = {
            str(r.get("journal_id", ""))
            for r in matches_list
            if _normalize_text(r.get("Status")) == "active" and _normalize_text(r.get("journal_id")) != ""
        }
        all_adjustments = adjustments_df.to_dict(orient="records")
        keep_adjustments: list[dict[str, Any]] = [r for r in all_adjustments if str(r.get("journal_id", "")).strip() != ""]

        for raw in rows:
            if not isinstance(raw, dict):
                continue
            day = _normalize_trade_day(raw.get("TradeDay"))
            _require_pre_trade_plan_completed(day)
            journal_id = _normalize_text(raw.get("journal_id")) or f"jrnl_{uuid.uuid4().hex[:12]}"
            seq = raw.get("SeqInDay")
            seq_in_day = int(pd.to_numeric(seq, errors="coerce")) if str(seq or "").strip() else _next_seq_for_day(journal, day)

            existing = by_id.get(journal_id, {})
            is_insert = journal_id not in by_id
            requested_match_status = _normalize_text(raw.get("MatchStatus"))
            existing_match_status = _normalize_text(existing.get("MatchStatus", "")) or "unmatched"
            contract_name = _normalize_text(raw.get("ContractName")) or _normalize_text(existing.get("ContractName")) or "MES"
            point_value = point_values.get(contract_name.upper())
            if point_value is None:
                raise ValueError(f"missing point_value for contract: {contract_name}")
            max_loss = _normalize_opt_num(raw.get("MaxLossUSD"))
            if max_loss == "":
                max_loss = _normalize_opt_num(existing.get("MaxLossUSD")) or "200.0"
            if float(max_loss) <= 0:
                raise ValueError("MaxLossUSD must be positive")
            direction = _normalize_direction(raw.get("Direction"))
            trade_intent = _normalize_text(raw.get("TradeIntent"))

            if "adjustments" in raw:
                mode = _normalize_text(raw.get("adjustments_mode")).lower() or "append"
                incoming, summary = _normalize_adjustments(
                    journal_id,
                    raw.get("adjustments"),
                    now_iso,
                    direction=direction,
                    trade_intent=trade_intent,
                    point_value=point_value,
                )
                if mode == "replace":
                    keep_adjustments = [r for r in keep_adjustments if str(r.get("journal_id", "")) != journal_id]
                    keep_adjustments.extend(incoming)
                else:
                    by_key: dict[tuple[str, str], dict[str, Any]] = {}
                    order: list[tuple[str, str]] = []
                    for r in keep_adjustments:
                        key = (str(r.get("journal_id", "")), str(r.get("adjustment_id", "")))
                        if key not in by_key:
                            order.append(key)
                        by_key[key] = dict(r)
                    for r in incoming:
                        key = (str(r.get("journal_id", "")), str(r.get("adjustment_id", "")))
                        if key in by_key:
                            prev = by_key[key]
                            next_adj = dict(r)
                            next_adj["CreatedAt"] = _normalize_text(prev.get("CreatedAt")) or next_adj["CreatedAt"]
                            by_key[key] = next_adj
                        else:
                            by_key[key] = dict(r)
                            order.append(key)
                    keep_adjustments = [by_key[k] for k in order]
            else:
                # Existing row updates without detail payload are not supported to avoid stale size/risk.
                raise ValueError("adjustments (execution detail rows) are required")

            rule_status = "ok"
            if summary.get("PotentialRiskUSD"):
                if float(summary["PotentialRiskUSD"]) > float(max_loss):
                    rule_status = "violation_max_loss"

            next_row = {
                "journal_id": journal_id,
                "TradeDay": day,
                "SeqInDay": str(max(1, seq_in_day)),
                "ContractName": contract_name,
                "Phase": _normalize_text(raw.get("Phase")),
                "Context": _normalize_text(raw.get("Context")),
                "Setup": _normalize_text(raw.get("Setup")),
                "SignalBar": _normalize_text(raw.get("SignalBar")),
                "TradeIntent": trade_intent,
                "Direction": direction,
                "Size": _normalize_size(summary.get("Size")),
                "MaxLossUSD": max_loss,
                "EnteredAt": summary.get("EnteredAt", ""),
                "ExitedAt": summary.get("ExitedAt", ""),
                "EntryPrice": summary.get("EntryPrice", ""),
                "TakeProfitPrice": summary.get("TakeProfitPrice", ""),
                "StopLossPrice": summary.get("StopLossPrice", ""),
                "ExitPrice": summary.get("ExitPrice", ""),
                "PotentialRiskUSD": summary.get("PotentialRiskUSD", ""),
                "PotentialRewardUSD": summary.get("PotentialRewardUSD", ""),
                "WinLossRatio": summary.get("WinLossRatio", ""),
                "RuleStatus": rule_status,
                "Notes": _normalize_text(raw.get("Notes")),
                "MatchStatus": requested_match_status or existing_match_status,
                "CreatedAt": existing.get("CreatedAt", now_iso),
                "UpdatedAt": now_iso,
            }

            # Hard-required execution/journal fields.
            required = ["Phase", "Context", "Setup", "SignalBar", "TradeIntent"]
            missing = [f for f in required if _normalize_text(next_row.get(f, "")) == ""]
            if missing:
                raise ValueError(f"missing required fields: {', '.join(missing)}")

            if existing:
                if journal_id in active_journal_ids:
                    raise ValueError("journal is linked to an active trade; unlink first before editing")

            if is_insert:
                latest = _latest_row_for_day(by_id, day)
                if latest is not None and _normalize_text(latest.get("ExitPrice", "")) == "":
                    latest_id = _normalize_text(latest.get("journal_id"))
                    raise ValueError(
                        f"cannot add next journal on {day}: previous journal {latest_id} is not closed (ExitPrice required)"
                    )
                status_rows = _rows_with_adjustments(by_id, keep_adjustments)
                day_status_before = _status_by_day(status_rows, point_values=point_values).get(day, {})
                if bool(day_status_before.get("max_trade_reached")):
                    raise ValueError(
                        f"daily max trade limit reached for {day}: "
                        f"{int(day_status_before.get('trade_count', 0))}/{int(day_status_before.get('daily_max_trade', DEFAULT_DAILY_MAX_TRADE))}"
                    )
                if bool(day_status_before.get("max_loss_reached")):
                    raise ValueError(
                        f"daily max loss limit reached for {day}: "
                        f"${float(day_status_before.get('cumulative_loss_usd', 0.0)):.2f}/"
                        f"${float(day_status_before.get('daily_max_loss', DEFAULT_DAILY_MAX_LOSS)):.2f}"
                    )

            if journal_id in by_id:
                updated += 1
            else:
                inserted += 1
            by_id[journal_id] = next_row
            changed_ids.append(journal_id)

        out_journal = _ensure_journal_schema(pd.DataFrame(list(by_id.values()), columns=JOURNAL_COLUMNS))
        out_adjustments = _ensure_adjustment_schema(pd.DataFrame(keep_adjustments, columns=ADJUSTMENT_COLUMNS))
        atomic_write_csv(out_journal, JOURNAL_LIVE_CSV)
        atomic_write_csv(out_adjustments, JOURNAL_ADJUSTMENTS_CSV)

    append_audit_event(
        "live_journal_upserted",
        {
            "journal_csv": JOURNAL_LIVE_CSV,
            "adjustments_csv": JOURNAL_ADJUSTMENTS_CSV,
            "rows_requested": len(rows),
            "inserted": inserted,
            "updated": updated,
            "journal_ids": changed_ids[:200],
            "needs_reconfirm_journal_ids": [],
            "inactivated_matches": 0,
        },
        actor=actor,
    )
    return {"inserted": inserted, "updated": updated}


def _compute_match_score(journal_row: dict[str, Any], perf_row: dict[str, Any], perf_index: int, journal_index: int) -> tuple[float, str]:
    score = 0.0
    match_type = "sequence"

    j_entry = pd.to_numeric(journal_row.get("EntryPrice"), errors="coerce")
    p_entry = pd.to_numeric(perf_row.get("EntryPrice"), errors="coerce")
    j_exit = pd.to_numeric(journal_row.get("ExitPrice"), errors="coerce")
    p_exit = pd.to_numeric(perf_row.get("ExitPrice"), errors="coerce")
    if pd.notna(j_entry) and pd.notna(p_entry):
        score += max(0.0, 50.0 - (abs(float(j_entry) - float(p_entry)) * 100))
        match_type = "price"
    if pd.notna(j_exit) and pd.notna(p_exit):
        score += max(0.0, 50.0 - (abs(float(j_exit) - float(p_exit)) * 100))
        match_type = "price"

    j_dir = _normalize_text(journal_row.get("Direction")).lower()
    p_dir = _normalize_text(perf_row.get("Type")).lower()
    if j_dir and p_dir and j_dir == p_dir:
        score += 20.0

    j_size = pd.to_numeric(journal_row.get("Size"), errors="coerce")
    p_size = pd.to_numeric(perf_row.get("Size"), errors="coerce")
    if pd.notna(j_size) and pd.notna(p_size):
        score += max(0.0, 15.0 - (abs(float(j_size) - float(p_size)) * 5))

    # Sequence fallback keeps ranking stable if prices/times are missing.
    seq_gap = abs(journal_index - perf_index)
    score += max(0.0, 15.0 - (seq_gap * 2))
    return score, match_type


def _perf_trade_day_key(raw: object) -> str:
    s = _normalize_text(raw)
    if not s:
        return ""
    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.date().isoformat()


def _journal_realized_pnl(
    journal_row: dict[str, Any],
    adjustments: list[dict[str, Any]],
    point_values: dict[str, float],
) -> float:
    direction = _normalize_text(journal_row.get("Direction")).title()
    if direction not in DIRECTION_VALUES:
        raise ValueError("journal direction is invalid")
    contract = _normalize_text(journal_row.get("ContractName")).upper()
    point_value = point_values.get(contract)
    if point_value is None:
        raise ValueError(f"missing point_value for contract: {contract}")
    if not adjustments:
        raise ValueError("journal adjustments are missing")
    total = 0.0
    for a in adjustments:
        qty = pd.to_numeric(a.get("Qty"), errors="coerce")
        entry = pd.to_numeric(a.get("EntryPrice"), errors="coerce")
        exit_px = pd.to_numeric(a.get("ExitPrice"), errors="coerce")
        if pd.isna(qty) or float(qty) <= 0:
            raise ValueError("journal adjustment Qty is invalid")
        if pd.isna(entry):
            raise ValueError("journal adjustment EntryPrice is invalid")
        if pd.isna(exit_px):
            raise ValueError("journal adjustment ExitPrice is required for matching")
        q = float(qty)
        e = float(entry)
        x = float(exit_px)
        leg = (x - e) * point_value * q if direction == "Long" else (e - x) * point_value * q
        total += leg
    return float(total)


def _performance_gross_pnl(perf_row: dict[str, Any]) -> float:
    pnl_net = pd.to_numeric(perf_row.get("PnL(Net)"), errors="coerce")
    if pd.isna(pnl_net):
        pnl_net = pd.to_numeric(perf_row.get("PnL"), errors="coerce")
    fees = pd.to_numeric(perf_row.get("Fees"), errors="coerce")
    if pd.isna(pnl_net):
        raise ValueError("performance PnL is missing")
    if pd.isna(fees):
        fees = 0.0
    return float(pnl_net) + float(fees)


def _validate_gross_pnl_match(
    journal_id: str,
    trade_id: str,
    trade_day: str,
    journal_rows: list[dict[str, Any]],
    adjustment_rows: list[dict[str, Any]],
    perf_rows: list[dict[str, Any]],
    point_values: dict[str, float],
) -> None:
    day = _normalize_trade_day(trade_day)
    j = next((r for r in journal_rows if _normalize_text(r.get("journal_id")) == journal_id), None)
    if not j:
        raise ValueError(f"journal row not found: {journal_id}")
    j_day = _normalize_trade_day(j.get("TradeDay"))
    if j_day != day:
        raise ValueError(f"journal day mismatch for {journal_id}: {j_day} != {day}")
    perf = next(
        (
            r
            for r in perf_rows
            if _normalize_text(r.get("trade_id")) == trade_id and _perf_trade_day_key(r.get("TradeDay")) == day
        ),
        None,
    )
    if not perf:
        raise ValueError(f"performance trade not found for trade_id={trade_id} on {day}")

    adj = [r for r in adjustment_rows if _normalize_text(r.get("journal_id")) == journal_id]
    journal_pnl = _journal_realized_pnl(j, adj, point_values)
    perf_gross = _performance_gross_pnl(perf)
    if abs(journal_pnl - perf_gross) > float(GROSS_PNL_TOLERANCE):
        raise ValueError(
            f"gross pnl mismatch for journal {journal_id} vs trade {trade_id}: "
            f"journal={journal_pnl:.2f}, performance_gross={perf_gross:.2f}, tol={GROSS_PNL_TOLERANCE:.2f}"
        )



def confirm_matches(
    trade_day: str,
    links: list[dict[str, Any]],
    *,
    replace_for_journal: bool = True,
    performance_rows: list[dict[str, Any]] | None = None,
    actor: str = "api:/journal/matching/confirm",
) -> dict[str, int]:
    day = _normalize_trade_day(trade_day)
    if not isinstance(links, list):
        raise ValueError("links must be an array")
    now_iso = _now_local_iso()
    inserted = 0
    inactivated = 0
    journal_rows = load_journal_live().to_dict(orient="records")
    adjustment_rows = load_journal_adjustments().to_dict(orient="records")
    point_values = _load_point_values()
    if performance_rows is None:
        perf_df = ensure_trade_id(pd.read_csv(PERFORMANCE_CSV)) if pd.io.common.file_exists(PERFORMANCE_CSV) else pd.DataFrame()
        perf_rows = perf_df.to_dict(orient="records")
    else:
        perf_rows = ensure_trade_id(pd.DataFrame(performance_rows)).to_dict(orient="records")

    with advisory_file_lock(JOURNAL_MATCHES_CSV):
        matches = load_journal_matches()
        matches_list = matches.to_dict(orient="records")

        for raw in links:
            if not isinstance(raw, dict):
                continue
            journal_id = _normalize_text(raw.get("journal_id"))
            trade_id = _normalize_text(raw.get("trade_id"))
            if not journal_id or not trade_id:
                raise ValueError("journal_id and trade_id are required")
            _validate_gross_pnl_match(
                journal_id,
                trade_id,
                day,
                journal_rows,
                adjustment_rows,
                perf_rows,
                point_values,
            )

            same_active_exists = any(
                _normalize_text(r.get("journal_id")) == journal_id
                and _normalize_text(r.get("trade_id")) == trade_id
                and _normalize_text(r.get("TradeDay")) == day
                and _normalize_text(r.get("Status")) == "active"
                for r in matches_list
            )
            if same_active_exists:
                continue

            if replace_for_journal:
                for row in matches_list:
                    if (
                        _normalize_text(row.get("journal_id")) == journal_id
                        and _normalize_text(row.get("TradeDay")) == day
                        and _normalize_text(row.get("Status")) == "active"
                    ):
                        row["Status"] = "inactive"
                        row["UpdatedAt"] = now_iso
                        inactivated += 1

            matches_list.append(
                {
                    "match_id": f"m_{uuid.uuid4().hex[:12]}",
                    "journal_id": journal_id,
                    "trade_id": trade_id,
                    "TradeDay": day,
                    "MatchType": _normalize_text(raw.get("match_type")) or "manual",
                    "Score": str(pd.to_numeric(raw.get("score"), errors="coerce") if raw.get("score") is not None else 0.0),
                    "IsPrimary": "true" if bool(raw.get("is_primary", True)) else "false",
                    "Status": "active",
                    "CreatedAt": now_iso,
                    "UpdatedAt": now_iso,
                }
            )
            inserted += 1

        out_matches = _ensure_match_schema(pd.DataFrame(matches_list, columns=MATCH_COLUMNS))
        atomic_write_csv(out_matches, JOURNAL_MATCHES_CSV)

        # Update journal match status.
        journal = load_journal_live()
        if not journal.empty:
            active = out_matches[(out_matches["TradeDay"] == day) & (out_matches["Status"] == "active")].copy()
            matched_ids = set(active["journal_id"].astype(str))
            day_mask = journal["TradeDay"] == day
            if day_mask.any():
                journal.loc[day_mask, "MatchStatus"] = journal.loc[day_mask, "journal_id"].astype(str).map(
                    lambda jid: "matched" if jid in matched_ids else "unmatched"
                )
                journal.loc[day_mask, "UpdatedAt"] = now_iso
                atomic_write_csv(_ensure_journal_schema(journal), JOURNAL_LIVE_CSV)

    append_audit_event(
        "journal_matches_confirmed",
        {
            "trade_day": day,
            "links_requested": len(links),
            "inserted": inserted,
            "inactivated": inactivated,
        },
        actor=actor,
    )
    return {"inserted": inserted, "inactivated": inactivated}


def unlink_matches(
    journal_id: str,
    *,
    trade_id: str | None = None,
    trade_day: str | None = None,
    actor: str = "api:/journal/matching/unlink",
) -> dict[str, int]:
    j_id = _normalize_text(journal_id)
    if not j_id:
        raise ValueError("journal_id is required")
    t_id = _normalize_text(trade_id)
    day = _normalize_trade_day(trade_day) if _normalize_text(trade_day) else ""
    now_iso = _now_local_iso()
    inactivated = 0

    with advisory_file_lock(JOURNAL_MATCHES_CSV):
        matches = load_journal_matches()
        rows = matches.to_dict(orient="records")
        for row in rows:
            if _normalize_text(row.get("journal_id")) != j_id:
                continue
            if t_id and _normalize_text(row.get("trade_id")) != t_id:
                continue
            if day and _normalize_text(row.get("TradeDay")) != day:
                continue
            if _normalize_text(row.get("Status")) != "active":
                continue
            row["Status"] = "inactive"
            row["UpdatedAt"] = now_iso
            inactivated += 1

        out_matches = _ensure_match_schema(pd.DataFrame(rows, columns=MATCH_COLUMNS))
        atomic_write_csv(out_matches, JOURNAL_MATCHES_CSV)

        if inactivated > 0:
            with advisory_file_lock(JOURNAL_LIVE_CSV):
                journal = load_journal_live()
                if not journal.empty:
                    active_journal_ids = set(
                        out_matches[out_matches["Status"] == "active"]["journal_id"].astype(str).tolist()
                    )
                    mask = journal["journal_id"].astype(str) == j_id
                    if mask.any():
                        journal.loc[mask, "MatchStatus"] = journal.loc[mask, "journal_id"].astype(str).map(
                            lambda v: "matched" if v in active_journal_ids else "unmatched"
                        )
                        journal.loc[mask, "UpdatedAt"] = now_iso
                        atomic_write_csv(_ensure_journal_schema(journal), JOURNAL_LIVE_CSV)

    append_audit_event(
        "journal_matches_unlinked",
        {
            "journal_id": j_id,
            "trade_id": t_id,
            "trade_day": day,
            "inactivated": inactivated,
        },
        actor=actor,
    )
    return {"inactivated": inactivated}


def reconfirm_match(
    journal_id: str,
    *,
    trade_id: str | None = None,
    trade_day: str | None = None,
    performance_rows: list[dict[str, Any]] | None = None,
    actor: str = "api:/journal/matching/reconfirm",
) -> dict[str, int]:
    j_id = _normalize_text(journal_id)
    if not j_id:
        raise ValueError("journal_id is required")
    t_id = _normalize_text(trade_id)
    day = _normalize_trade_day(trade_day) if _normalize_text(trade_day) else ""
    now_iso = _now_local_iso()

    matches = load_journal_matches()
    active = matches[matches["Status"] == "active"].copy() if not matches.empty else pd.DataFrame(columns=MATCH_COLUMNS)
    if active.empty:
        raise ValueError("no active matches found")

    check = active[active["journal_id"].astype(str) == j_id].copy()
    if t_id:
        check = check[check["trade_id"].astype(str) == t_id].copy()
    if day:
        check = check[check["TradeDay"].astype(str) == day].copy()
    if check.empty:
        raise ValueError("no active link found for reconfirmation")

    journal_rows = load_journal_live().to_dict(orient="records")
    adjustment_rows = load_journal_adjustments().to_dict(orient="records")
    point_values = _load_point_values()
    if performance_rows is None:
        perf_df = ensure_trade_id(pd.read_csv(PERFORMANCE_CSV)) if pd.io.common.file_exists(PERFORMANCE_CSV) else pd.DataFrame()
        perf_rows = perf_df.to_dict(orient="records")
    else:
        perf_rows = ensure_trade_id(pd.DataFrame(performance_rows)).to_dict(orient="records")
    for _, row in check.iterrows():
        _validate_gross_pnl_match(
            j_id,
            _normalize_text(row.get("trade_id")),
            _normalize_text(row.get("TradeDay")),
            journal_rows,
            adjustment_rows,
            perf_rows,
            point_values,
        )

    with advisory_file_lock(JOURNAL_LIVE_CSV):
        journal = load_journal_live()
        if journal.empty:
            raise ValueError("journal row not found")
        mask = journal["journal_id"].astype(str) == j_id
        if not mask.any():
            raise ValueError("journal row not found")
        changed = int(mask.sum())
        journal.loc[mask, "MatchStatus"] = "matched"
        journal.loc[mask, "UpdatedAt"] = now_iso
        atomic_write_csv(_ensure_journal_schema(journal), JOURNAL_LIVE_CSV)

    append_audit_event(
        "journal_match_reconfirmed",
        {
            "journal_id": j_id,
            "trade_id": t_id,
            "trade_day": day,
            "updated_rows": changed,
        },
        actor=actor,
    )
    return {"updated": changed}
