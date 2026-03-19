from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any
import uuid

import pandas as pd

from dashboard.config.analysis import ANALYSIS_TIMEZONE
from dashboard.config.settings import JOURNAL_LIVE_CSV, JOURNAL_ADJUSTMENTS_CSV, JOURNAL_MATCHES_CSV, CONTRACT_SPECS_CSV
from dashboard.services.utils.persistence import advisory_file_lock, atomic_write_csv, append_audit_event

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


def upsert_live_journal_rows(rows: list[dict[str, Any]], *, actor: str = "api:/journal/live") -> dict[str, int]:
    if not isinstance(rows, list):
        raise ValueError("rows must be an array")
    inserted = 0
    updated = 0
    changed_ids: list[str] = []
    now_iso = _now_local_iso()
    critical_fields = ["TradeDay", "Direction", "Size", "EnteredAt", "ExitedAt", "EntryPrice", "ExitPrice", "ContractName"]
    rematch_required_ids: set[str] = set()
    inactivated_matches = 0
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
            journal_id = _normalize_text(raw.get("journal_id")) or f"jrnl_{uuid.uuid4().hex[:12]}"
            seq = raw.get("SeqInDay")
            seq_in_day = int(pd.to_numeric(seq, errors="coerce")) if str(seq or "").strip() else _next_seq_for_day(journal, day)

            existing = by_id.get(journal_id, {})
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
                changed_critical = any(_normalize_text(existing.get(f, "")) != _normalize_text(next_row.get(f, "")) for f in critical_fields)
                if changed_critical and journal_id in active_journal_ids:
                    next_row["MatchStatus"] = "needs_reconfirm"
                    rematch_required_ids.add(journal_id)

            if journal_id in by_id:
                updated += 1
            else:
                inserted += 1
            by_id[journal_id] = next_row
            changed_ids.append(journal_id)

        if rematch_required_ids:
            for row in matches_list:
                if (
                    _normalize_text(row.get("journal_id")) in rematch_required_ids
                    and _normalize_text(row.get("Status")) == "active"
                ):
                    row["Status"] = "inactive"
                    row["UpdatedAt"] = now_iso
                    inactivated_matches += 1

        out_journal = _ensure_journal_schema(pd.DataFrame(list(by_id.values()), columns=JOURNAL_COLUMNS))
        out_adjustments = _ensure_adjustment_schema(pd.DataFrame(keep_adjustments, columns=ADJUSTMENT_COLUMNS))
        atomic_write_csv(out_journal, JOURNAL_LIVE_CSV)
        atomic_write_csv(out_adjustments, JOURNAL_ADJUSTMENTS_CSV)
        if rematch_required_ids:
            with advisory_file_lock(JOURNAL_MATCHES_CSV):
                out_matches = _ensure_match_schema(pd.DataFrame(matches_list, columns=MATCH_COLUMNS))
                atomic_write_csv(out_matches, JOURNAL_MATCHES_CSV)

    append_audit_event(
        "live_journal_upserted",
        {
            "journal_csv": JOURNAL_LIVE_CSV,
            "adjustments_csv": JOURNAL_ADJUSTMENTS_CSV,
            "rows_requested": len(rows),
            "inserted": inserted,
            "updated": updated,
            "journal_ids": changed_ids[:200],
            "needs_reconfirm_journal_ids": sorted(rematch_required_ids),
            "inactivated_matches": inactivated_matches,
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



def confirm_matches(
    trade_day: str,
    links: list[dict[str, Any]],
    *,
    replace_for_journal: bool = True,
    actor: str = "api:/journal/matching/confirm",
) -> dict[str, int]:
    day = _normalize_trade_day(trade_day)
    if not isinstance(links, list):
        raise ValueError("links must be an array")
    now_iso = _now_local_iso()
    inserted = 0
    inactivated = 0

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
