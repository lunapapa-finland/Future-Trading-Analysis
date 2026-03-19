"""
Lightweight JSON API shim exposing existing analytics for the new frontend.

Routes:
- GET /api/candles            -> raw 5m OHLCV from CSV
- GET /api/performance/combined -> combined performance CSV
- POST /api/analysis/<metric> -> wraps functions in dashboard.analysis.compute
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from flask import Blueprint, jsonify, request

from dashboard.services.analysis import compute
from dashboard.services.analysis.behavioral import behavior_heatmap
from dashboard.services.analysis.plots import get_statistics
from dashboard.config.settings import DATA_SOURCE_DROPDOWN, PERFORMANCE_CSV, SYMBOL_CATALOG, CONTRACT_SPECS_CSV
from dashboard.config.env import TIMEFRAME_OPTIONS, PLAYBACK_SPEEDS
from dashboard.config.env import TEMP_PERF_DIR
from dashboard.config.analysis import (
    RISK_FREE_RATE,
    INITIAL_NET_LIQ,
    PORTFOLIO_START_DATE,
    RULE_COMPLIANCE_DEFAULTS,
    ANALYSIS_TIMEZONE,
)
from dashboard.config.app_config import get_app_config
from dashboard.config.runtime_manifest import runtime_manifest
from dashboard.services.data.load_data import load_performance, load_future
from dashboard.services.portfolio import equity_series, append_manual
from dashboard.services.analysis.portfolio_metrics import portfolio_metrics
from dashboard.services.utils.trade_enrichment import ensure_trade_id, merge_trade_labels
from dashboard.services.utils.tag_taxonomy import taxonomy_payload
from dashboard.services.utils.day_plan_taxonomy import day_plan_taxonomy_payload
from dashboard.services.utils.day_plan import list_day_plan, upsert_day_plan_rows
from dashboard.services.utils.performance_acquisition import process_csv, generate_aggregated_data
from dashboard.services.utils.journal_live import (
    list_live_journal,
    upsert_live_journal_rows,
    confirm_matches,
    list_active_matches,
    unlink_matches,
    load_journal_matches,
    load_journal_live,
    DIRECTION_VALUES,
)
from dashboard.services.utils.persistence import advisory_file_lock, atomic_write_csv, append_audit_event
from dashboard.services.utils.datetime_utils import (
    parse_optional_timestamp_utc,
    parse_optional_date_in_timezone,
    ensure_valid_range,
    normalize_series_utc,
    normalize_series_to_timezone,
    iso_utc,
)
import numpy as np


VALID_GRANULARITIES = {"1D", "1W-MON", "1M"}
VALID_METRICS = {
    "behavioral_heatmap",
    "pnl_growth",
    "drawdown",
    "pnl_distribution",
    "behavioral_patterns",
    "rolling_win_rate",
    "sharpe_ratio",
    "trade_efficiency",
    "hourly_performance",
    "performance_envelope",
    "overtrading_detection",
    "kelly_criterion",
}


def _cors_headers(response, allowed_origin: str):
    response.headers["Access-Control-Allow-Origin"] = allowed_origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Vary"] = "Origin"
    return response


def _iso_in_timezone(value: object, tz_name: str) -> str:
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.tz_convert(tz_name).isoformat()


def _require_json_object() -> Dict[str, Any]:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def _effective_key(df: pd.DataFrame) -> pd.Series:
    out = df.copy()
    if "trade_id" not in out.columns:
        out["trade_id"] = ""
    for col in ["TradeDay", "ContractName", "IntradayIndex"]:
        if col not in out.columns:
            out[col] = ""
    out["trade_id"] = out["trade_id"].fillna("").astype(str).str.strip()
    out["TradeDay"] = out["TradeDay"].fillna("").astype(str).str.strip()
    out["ContractName"] = out["ContractName"].fillna("").astype(str).str.strip()
    out["IntradayIndex"] = pd.to_numeric(out["IntradayIndex"], errors="coerce").fillna(-1).astype(int).astype(str)
    legacy = out["TradeDay"] + "|" + out["ContractName"] + "|" + out["IntradayIndex"]
    return out["trade_id"].where(out["trade_id"] != "", legacy)


def _validate_symbol(symbol: Optional[str], *, required: bool = False) -> Optional[str]:
    if symbol is None or str(symbol).strip() == "":
        if required:
            raise ValueError("symbol is required")
        return None
    symbol = str(symbol).strip()
    if symbol not in SYMBOL_CATALOG:
        raise ValueError(f"unknown symbol {symbol}")
    return symbol


def _parse_range(start_raw: Optional[str], end_raw: Optional[str], *, normalize_date: bool = False) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    if normalize_date:
        start = parse_optional_date_in_timezone(start_raw, "start", ANALYSIS_TIMEZONE)
        end = parse_optional_date_in_timezone(end_raw, "end", ANALYSIS_TIMEZONE)
    else:
        start = parse_optional_timestamp_utc(start_raw, "start")
        end = parse_optional_timestamp_utc(end_raw, "end")
    ensure_valid_range(start, end)
    return start, end


def _to_float(v: object) -> Optional[float]:
    n = pd.to_numeric(v, errors="coerce")
    if pd.isna(n):
        return None
    return float(n)


def _parse_ts_central(v: object) -> Optional[pd.Timestamp]:
    s = str(v or "").strip()
    if not s:
        return None
    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts):
        return None
    if getattr(ts, "tzinfo", None) is None:
        return ts.tz_localize(ANALYSIS_TIMEZONE)
    return ts.tz_convert(ANALYSIS_TIMEZONE)


def _pair_match_tiered(journal_row: dict[str, Any], perf_row: dict[str, Any], perf_index: int, journal_index: int) -> dict[str, Any]:
    # Tier 1: journal-maintained time (fuzzy) + price (exact) signals.
    j_entry_ts = _parse_ts_central(journal_row.get("EnteredAt"))
    p_entry_ts = _parse_ts_central(perf_row.get("EnteredAt"))
    j_exit_ts = _parse_ts_central(journal_row.get("ExitedAt"))
    p_exit_ts = _parse_ts_central(perf_row.get("ExitedAt"))
    j_entry_px = _to_float(journal_row.get("EntryPrice"))
    p_entry_px = _to_float(perf_row.get("EntryPrice"))
    j_exit_px = _to_float(journal_row.get("ExitPrice"))
    p_exit_px = _to_float(perf_row.get("ExitPrice"))

    tier1_evidence = any(x is not None for x in [j_entry_ts, j_exit_ts, j_entry_px, j_exit_px])
    tier1_score = 0.0
    reasons: list[str] = []
    hard_conflict = False

    if j_entry_ts is not None and p_entry_ts is not None:
        diff_min = abs((j_entry_ts - p_entry_ts).total_seconds()) / 60.0
        if diff_min <= 1:
            tier1_score += 30
        elif diff_min <= 3:
            tier1_score += 24
        elif diff_min <= 5:
            tier1_score += 16
        elif diff_min <= 10:
            tier1_score += 8
        reasons.append(f"entry_time_diff_min={diff_min:.2f}")
    if j_exit_ts is not None and p_exit_ts is not None:
        diff_min = abs((j_exit_ts - p_exit_ts).total_seconds()) / 60.0
        if diff_min <= 1:
            tier1_score += 30
        elif diff_min <= 3:
            tier1_score += 24
        elif diff_min <= 5:
            tier1_score += 16
        elif diff_min <= 10:
            tier1_score += 8
        reasons.append(f"exit_time_diff_min={diff_min:.2f}")
    if j_entry_px is not None and p_entry_px is not None:
        if abs(j_entry_px - p_entry_px) < 1e-9:
            tier1_score += 35
            reasons.append("entry_price_exact=true")
        else:
            hard_conflict = True
            tier1_score -= 120
            reasons.append("entry_price_exact=false")
    if j_exit_px is not None and p_exit_px is not None:
        if abs(j_exit_px - p_exit_px) < 1e-9:
            tier1_score += 35
            reasons.append("exit_price_exact=true")
        else:
            hard_conflict = True
            tier1_score -= 120
            reasons.append("exit_price_exact=false")

    # Tier 2: direction + size exact.
    j_dir = str(journal_row.get("Direction", "")).strip().lower()
    p_dir = str(perf_row.get("Type", "")).strip().lower()
    j_size = _to_float(journal_row.get("Size"))
    p_size = _to_float(perf_row.get("Size"))
    dir_exact = bool(j_dir and p_dir and j_dir == p_dir)
    size_exact = bool(j_size is not None and p_size is not None and abs(j_size - p_size) < 1e-9)

    tier2_score = 0.0
    if dir_exact:
        tier2_score += 25
    else:
        tier2_score -= 8
    if size_exact:
        tier2_score += 25
    else:
        tier2_score -= 8
    reasons.append(f"direction_exact={str(dir_exact).lower()}")
    reasons.append(f"size_exact={str(size_exact).lower()}")

    # Sequence fallback is tier 3 manual-assist only.
    seq_gap = abs(journal_index - perf_index)
    tier3_score = max(0.0, 15.0 - (seq_gap * 2.0))
    reasons.append(f"sequence_gap={seq_gap}")

    if tier1_evidence:
        tier = 1
        score = tier1_score + (0.25 * tier2_score) + (0.1 * tier3_score)
        match_type = "tier1_time_price"
    elif dir_exact or size_exact:
        tier = 2
        score = tier2_score + (0.25 * tier3_score)
        match_type = "tier2_dir_size"
    else:
        tier = 3
        score = tier3_score
        match_type = "tier3_manual"

    if hard_conflict:
        score -= 1000.0

    return {
        "tier": tier,
        "score": round(float(score), 4),
        "match_type": match_type,
        "hard_conflict": hard_conflict,
        "reasons": reasons,
    }


def _validate_metric_payload(metric: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if metric not in VALID_METRICS:
        raise ValueError(f"unknown metric {metric}")
    if "granularity" in payload and payload.get("granularity") is not None:
        granularity = str(payload["granularity"])
        if granularity not in VALID_GRANULARITIES:
            raise ValueError(f"granularity must be one of {sorted(VALID_GRANULARITIES)}")
    if "window" in payload and payload.get("window") is not None:
        try:
            payload["window"] = int(payload["window"])
        except (TypeError, ValueError):
            raise ValueError("window must be a positive integer")
        if int(payload["window"]) < 1:
            raise ValueError("window must be a positive integer")
    params = payload.get("params")
    if params is not None and not isinstance(params, dict):
        raise ValueError("params must be an object")
    payload["params"] = params or {}
    payload["include_unmatched"] = bool(payload.get("include_unmatched", False))
    payload["symbol"] = _validate_symbol(payload.get("symbol"), required=False)
    start, end = _parse_range(payload.get("start_date"), payload.get("end_date"), normalize_date=True)
    payload["start_date"] = start
    payload["end_date"] = end
    return payload


def _active_match_trade_ids(start: Optional[pd.Timestamp], end: Optional[pd.Timestamp]) -> set[str]:
    matches = load_journal_matches()
    if matches.empty:
        return set()
    active = matches[matches["Status"] == "active"].copy()
    if active.empty:
        return set()
    if start is not None:
        active = active[active["TradeDay"] >= start.date().isoformat()].copy()
    if end is not None:
        active = active[active["TradeDay"] <= end.date().isoformat()].copy()
    if active.empty:
        return set()
    return set(active["trade_id"].fillna("").astype(str).str.strip())


def _live_journal_label_map(start: Optional[pd.Timestamp], end: Optional[pd.Timestamp]) -> pd.DataFrame:
    matches = load_journal_matches()
    journal = load_journal_live()
    if matches.empty or journal.empty:
        return pd.DataFrame(columns=["trade_id", "Phase", "Context", "Setup", "SignalBar", "TradeIntent", "JournalId"])

    active = matches[matches["Status"] == "active"].copy()
    if active.empty:
        return pd.DataFrame(columns=["trade_id", "Phase", "Context", "Setup", "SignalBar", "TradeIntent", "JournalId"])
    if start is not None:
        active = active[active["TradeDay"] >= start.date().isoformat()].copy()
    if end is not None:
        active = active[active["TradeDay"] <= end.date().isoformat()].copy()
    if active.empty:
        return pd.DataFrame(columns=["trade_id", "Phase", "Context", "Setup", "SignalBar", "TradeIntent", "JournalId"])

    active["__primary"] = active["IsPrimary"].astype(str).str.lower().isin(["1", "true", "yes", "y"])
    active["__updated"] = pd.to_datetime(active["UpdatedAt"], errors="coerce")
    active = active.sort_values(["trade_id", "__primary", "__updated"], ascending=[True, False, False], kind="stable")
    active = active.drop_duplicates(subset=["trade_id"], keep="first")

    journal_cols = ["journal_id", "Phase", "Context", "Setup", "SignalBar", "TradeIntent"]
    j = journal[journal_cols].copy()
    j["journal_id"] = j["journal_id"].astype(str).str.strip()
    merged = active.merge(j, on="journal_id", how="left")
    merged["trade_id"] = merged["trade_id"].astype(str).str.strip()
    out = merged.rename(columns={"journal_id": "JournalId"})[
        ["trade_id", "Phase", "Context", "Setup", "SignalBar", "TradeIntent", "JournalId"]
    ].copy()
    for col in ["Phase", "Context", "Setup", "SignalBar", "TradeIntent", "JournalId"]:
        out[col] = out[col].fillna("").astype(str).str.strip()
    out = out[out["trade_id"] != ""].copy()
    return out


def _apply_live_journal_labels(df: pd.DataFrame, start: Optional[pd.Timestamp], end: Optional[pd.Timestamp]) -> pd.DataFrame:
    if df.empty or "trade_id" not in df.columns:
        return df
    labels = _live_journal_label_map(start, end)
    if labels.empty:
        return df

    merged = df.merge(labels, on="trade_id", how="left", suffixes=("", "__live"))
    for col in ["Phase", "Context", "Setup", "SignalBar", "TradeIntent"]:
        live_col = f"{col}__live"
        if col not in merged.columns:
            merged[col] = ""
        if live_col in merged.columns:
            merged[col] = np.where(
                merged[live_col].fillna("").astype(str).str.strip() != "",
                merged[live_col],
                merged[col],
            )
            merged.drop(columns=[live_col], inplace=True, errors="ignore")
    if "JournalId" not in merged.columns and "JournalId__live" in merged.columns:
        merged = merged.rename(columns={"JournalId__live": "JournalId"})
    elif "JournalId__live" in merged.columns:
        merged.drop(columns=["JournalId__live"], inplace=True, errors="ignore")
    return merged


def register_api(server):
    allowed_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:8050")
    if allowed_origin == "*":
        allowed_origin = "http://localhost:8050"
    api = Blueprint("api", __name__, url_prefix="/api")

    @api.after_request
    def add_cors(resp):  # type: ignore
        return _cors_headers(resp, allowed_origin)

    @api.route("/config", methods=["GET"])
    def config():
        symbols = []
        for symbol, cfg in SYMBOL_CATALOG.items():
            if not cfg.get("enabled", True):
                continue
            symbols.append(
                {
                    "symbol": symbol,
                    "data_path": cfg.get("data_path"),
                    "performance_path": cfg.get("performance_path", PERFORMANCE_CSV),
                    "asset_class": cfg.get("asset_class", "unknown"),
                    "source": cfg.get("source", {}),
                    "exchange": cfg.get("exchange"),
                    "timezone": cfg.get("timezone"),
                }
            )
        return jsonify(
            {
                "symbols": symbols,
                "timeframes": TIMEFRAME_OPTIONS,
                "playback_speeds": PLAYBACK_SPEEDS,
                "portfolio": {
                    "initial_net_liq": INITIAL_NET_LIQ,
                    "start_date": PORTFOLIO_START_DATE,
                    "risk_free_rate": RISK_FREE_RATE,
                },
                "insights_defaults": {
                    "rule_compliance": RULE_COMPLIANCE_DEFAULTS,
                },
                "tag_taxonomy": taxonomy_payload(),
                "day_plan_taxonomy": day_plan_taxonomy_payload(),
                "runtime_manifest": runtime_manifest(),
            }
        )

    @api.route("/tags/taxonomy", methods=["GET", "OPTIONS"])
    def tags_taxonomy():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            return jsonify(taxonomy_payload()), 200
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"failed to load tag taxonomy: {exc}"}), 500

    @api.route("/day-plan/taxonomy", methods=["GET", "OPTIONS"])
    def day_plan_taxonomy():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            return jsonify(day_plan_taxonomy_payload()), 200
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"failed to load day-plan taxonomy: {exc}"}), 500

    @api.route("/portfolio", methods=["GET"])
    def portfolio():
        try:
            series = equity_series(limit=500)
            latest = series[-1] if series else None
            metrics = portfolio_metrics()
            return jsonify({"latest": latest, "series": series, "risk_free_rate": RISK_FREE_RATE, "metrics": metrics})
        except Exception as exc:
            return jsonify({"error": f"failed to load portfolio: {exc}"}), 500

    @api.route("/portfolio/adjust", methods=["POST"])
    def portfolio_adjust():
        try:
            payload = _require_json_object()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        reason = str(payload.get("reason", "")).lower().strip()
        try:
            amount = float(payload.get("amount", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "amount must be a number"}), 400
        if amount <= 0:
            return jsonify({"error": "amount must be positive"}), 400
        date_str = payload.get("date")
        if reason not in {"deposit", "withdraw"}:
            return jsonify({"error": "reason must be deposit or withdraw"}), 400
        if date_str:
            try:
                datetime.fromisoformat(date_str)
            except ValueError:
                return jsonify({"error": "date must be ISO format YYYY-MM-DD"}), 400
        if reason == "withdraw":
            amount = -abs(amount)
        else:
            amount = abs(amount)
        try:
            entry = append_manual(reason=reason, amount=amount, date_override=date_str)
            return jsonify({"ok": True, "entry": entry})
        except (ValueError, OSError) as exc:
            return jsonify({"error": f"failed to append: {exc}"}), 500

    @api.route("/candles", methods=["GET", "OPTIONS"])
    def candles():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)

        try:
            symbol = _validate_symbol(request.args.get("symbol"), required=True)
            if symbol is None:
                return jsonify({"error": "symbol is required"}), 400
            start, end = _parse_range(request.args.get("start"), request.args.get("end"), normalize_date=False)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        csv_path = DATA_SOURCE_DROPDOWN.get(symbol)
        if not os.path.exists(csv_path):
            return jsonify({"error": f"data not found for {symbol}"}), 404

        try:
            df = pd.read_csv(csv_path)
            df["Datetime"] = normalize_series_utc(df["Datetime"], "Datetime")
            if start:
                df = df[df["Datetime"] >= start]
            if end:
                df = df[df["Datetime"] <= end]
            df = df.sort_values("Datetime")
            has_volume = "Volume" in df.columns
            records = []
            for _, row in df.iterrows():
                records.append(
                    {
                        "time": iso_utc(row["Datetime"]),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row["Volume"]) if has_volume else None,
                    }
                )
            return jsonify(records)
        except (KeyError, ValueError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"failed to read candles: {exc}"}), 500

    @api.route("/performance/combined", methods=["GET", "OPTIONS"])
    def combined_performance():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        if not os.path.exists(PERFORMANCE_CSV):
            return jsonify({"error": "performance data not found"}), 404
        try:
            start, end = _parse_range(request.args.get("start"), request.args.get("end"), normalize_date=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            df = merge_trade_labels(ensure_trade_id(pd.read_csv(PERFORMANCE_CSV)))
            df = _apply_live_journal_labels(df, start, end)
            if start or end:
                if "TradeDay" in df.columns:
                    df["TradeDay"] = normalize_series_to_timezone(df["TradeDay"], "TradeDay", ANALYSIS_TIMEZONE).dt.normalize()
                    if start:
                        df = df[df["TradeDay"] >= start]
                    if end:
                        df = df[df["TradeDay"] <= end]
                elif "ExitedAt" in df.columns:
                    df["ExitedAt"] = normalize_series_utc(df["ExitedAt"], "ExitedAt").dt.tz_convert(ANALYSIS_TIMEZONE).dt.normalize()
                    if start:
                        df = df[df["ExitedAt"] >= start]
                    if end:
                        df = df[df["ExitedAt"] <= end]
            records = df.to_dict(orient="records")
            return jsonify(records)
        except (KeyError, ValueError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"failed to read performance: {exc}"}), 500

    def _load_performance_df(payload: Dict[str, Any]) -> pd.DataFrame:
        if not os.path.exists(PERFORMANCE_CSV):
            raise FileNotFoundError("performance data not found")
        df = merge_trade_labels(ensure_trade_id(pd.read_csv(PERFORMANCE_CSV)))
        symbol = payload.get("symbol")
        start = payload.get("start_date")
        end = payload.get("end_date")
        include_unmatched = bool(payload.get("include_unmatched", False))
        if start or end:
            if "TradeDay" in df.columns:
                df["TradeDay"] = normalize_series_to_timezone(df["TradeDay"], "TradeDay", ANALYSIS_TIMEZONE).dt.normalize()
                if start:
                    df = df[df["TradeDay"] >= start]
                if end:
                    df = df[df["TradeDay"] <= end]
            elif "ExitedAt" in df.columns:
                df["ExitedAt"] = normalize_series_utc(df["ExitedAt"], "ExitedAt").dt.tz_convert(ANALYSIS_TIMEZONE).dt.normalize()
                if start:
                    df = df[df["ExitedAt"] >= start]
                if end:
                    df = df[df["ExitedAt"] <= end]
        if symbol:
            if "ContractName" in df.columns:
                df = df[df["ContractName"].astype(str).str.startswith(symbol)]
            elif "Symbol" in df.columns:
                df = df[df["Symbol"] == symbol]

        df = _apply_live_journal_labels(df, start, end)
        if not include_unmatched and "trade_id" in df.columns:
            matched_ids = _active_match_trade_ids(start, end)
            if matched_ids:
                df = df[df["trade_id"].astype(str).isin(matched_ids)].copy()
            else:
                df = df.iloc[0:0].copy()
        return df

    def _to_records(df: pd.DataFrame) -> list[Dict[str, Any]]:
        return df.to_dict(orient="records")

    def _metric_handler(metric: str, df: pd.DataFrame, payload: Dict[str, Any]) -> Tuple[Any, int]:
        granularity = payload.get("granularity")
        window = payload.get("window")
        resolved_window = compute.DEFAULT_ROLLING_WINDOW if window is None else window
        params = payload.get("params") or {}

        if metric == "behavioral_heatmap":
            out = behavior_heatmap(df)
            return _to_records(out), 200
        elif metric == "pnl_growth":
            out = compute.pnl_growth(
                df,
                granularity=granularity or compute.DEFAULT_GRANULARITY,
                daily_compounding_rate=params.get("daily_compounding_rate", 0.001902),
                initial_funding=params.get("initial_funding", 10000),
            )
            return _to_records(out), 200
        elif metric == "drawdown":
            out = compute.drawdown(df, granularity=granularity or compute.DEFAULT_GRANULARITY)
            return _to_records(out), 200
        elif metric == "pnl_distribution":
            out = compute.pnl_distribution(df)
            return _to_records(out), 200
        elif metric == "behavioral_patterns":
            out = compute.behavioral_patterns(df)
            return _to_records(out), 200
        elif metric == "rolling_win_rate":
            out = compute.rolling_win_rate(df, window=resolved_window)
            return _to_records(out), 200
        elif metric == "sharpe_ratio":
            out = compute.sharpe_ratio(
                df,
                window=resolved_window,
                risk_free_rate=params.get("risk_free_rate", 0.02),
                initial_capital=params.get("initial_capital", INITIAL_NET_LIQ),
            )
            return _to_records(out), 200
        elif metric == "trade_efficiency":
            out = compute.trade_efficiency(df, window=resolved_window)
            return _to_records(out), 200
        elif metric == "hourly_performance":
            out = compute.hourly_performance(df)
            return _to_records(out), 200
        elif metric == "performance_envelope":
            theoretical, actual = compute.performance_envelope(df, granularity=granularity or compute.DEFAULT_GRANULARITY)
            return {"theoretical": _to_records(theoretical), "actual": _to_records(actual)}, 200
        elif metric == "overtrading_detection":
            daily, trades = compute.overtrading_detection(
                df,
                cap_loss_per_trade=params.get("cap_loss_per_trade", 200),
                cap_trades_after_big_loss=params.get("cap_trades_after_big_loss", 5),
            )
            return {"daily": _to_records(daily), "trades": _to_records(trades)}, 200
        elif metric == "kelly_criterion":
            out = compute.kelly_criterion(df)
            data = _to_records(out.get("data", pd.DataFrame()))
            return {"data": data, "metadata": out.get("metadata", {})}, 200
        return {"error": f"unknown metric {metric}"}, 400

    @api.route("/analysis/<metric>", methods=["POST", "OPTIONS"])
    def analysis(metric: str):
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            payload = _validate_metric_payload(metric, _require_json_object())
            df = _load_performance_df(payload)
            if df.empty:
                return jsonify({"error": "performance dataset is empty", "code": "EMPTY_DATASET"}), 400
            body, status = _metric_handler(metric, df, payload)
            return jsonify(body), status
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"analysis failed: {exc}"}), 500

    @api.route("/insights", methods=["POST", "OPTIONS"])
    def insights():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            payload = _require_json_object()
            payload["symbol"] = _validate_symbol(payload.get("symbol"), required=False)
            payload["include_unmatched"] = bool(payload.get("include_unmatched", False))
            params = payload.get("params")
            if params is not None and not isinstance(params, dict):
                raise ValueError("params must be an object")
            payload["params"] = params or {}
            start, end = _parse_range(payload.get("start_date"), payload.get("end_date"), normalize_date=True)
            payload["start_date"] = start
            payload["end_date"] = end
            df = _load_performance_df(payload)
            if df.empty:
                return jsonify({"error": "performance dataset is empty", "code": "EMPTY_DATASET"}), 400
            params = payload.get("params") or {}
            out = compute.insights_bundle(df, params=params)
            return jsonify(out), 200
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"insights failed: {exc}"}), 500

    @api.route("/journal/tags", methods=["POST", "OPTIONS"])
    @api.route("/journal/setup-tags", methods=["POST", "OPTIONS"])
    def journal_setup_tags():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            payload = _require_json_object()
            rows = payload.get("rows")
            if not isinstance(rows, list):
                raise ValueError("rows must be an array")
            if not os.path.exists(PERFORMANCE_CSV):
                raise FileNotFoundError("performance data not found")

            def _normalize_setups(v: Any) -> str:
                if isinstance(v, list):
                    vals = [str(x).strip() for x in v if str(x).strip()]
                else:
                    vals = [part.strip() for part in str(v or "").replace(";", "|").replace(",", "|").split("|") if part.strip()]
                out: list[str] = []
                seen: set[str] = set()
                for item in vals:
                    k = item.lower()
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(item)
                return " | ".join(out)

            def _normalize_text(v: Any) -> str:
                return str(v or "").strip()

            with advisory_file_lock(PERFORMANCE_CSV):
                perf_df = ensure_trade_id(pd.read_csv(PERFORMANCE_CSV))
                for col in ["TradeDay", "ContractName", "IntradayIndex", "Phase", "Context", "Setup", "SignalBar", "TradeIntent"]:
                    if col not in perf_df.columns:
                        perf_df[col] = ""
                perf_df["trade_id"] = perf_df["trade_id"].fillna("").astype(str).str.strip()
                perf_df["TradeDay"] = perf_df["TradeDay"].fillna("").astype(str).str.strip()
                perf_df["ContractName"] = perf_df["ContractName"].fillna("").astype(str).str.strip()
                perf_df["IntradayIndex"] = pd.to_numeric(perf_df["IntradayIndex"], errors="coerce").fillna(-1).astype(int).astype(str)
                perf_df["Phase"] = perf_df["Phase"].fillna("").astype(str).str.strip()
                perf_df["Context"] = perf_df["Context"].fillna("").astype(str).str.strip()
                perf_df["Setup"] = perf_df["Setup"].fillna("").astype(str).str.strip()
                perf_df["SignalBar"] = perf_df["SignalBar"].fillna("").astype(str).str.strip()
                perf_df["TradeIntent"] = perf_df["TradeIntent"].fillna("").astype(str).str.strip()
                perf_df["__effective_key"] = _effective_key(perf_df)
                updated = 0
                skipped = 0
                changed_keys: list[str] = []
                strict_mode = bool(get_app_config().get("tagging", {}).get("strict_mode", True))
                taxonomy = taxonomy_payload()
                allowed_phase = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("phase", [])}
                allowed_context = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("context", [])}
                allowed_setup = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("setup", [])}
                allowed_signal = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("signal_bar", [])}
                allowed_intent = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("trade_intent", [])}

                def _normalize_by_taxonomy(raw: str, allowed_map: Dict[str, str], field: str) -> str:
                    val = _normalize_text(raw)
                    if not strict_mode or val == "":
                        return val
                    if not allowed_map:
                        return val
                    key = val.lower()
                    if key not in allowed_map:
                        raise ValueError(f"invalid {field}: {val}")
                    return allowed_map[key]

                def _normalize_setups_by_taxonomy(raw: Any) -> str:
                    val = _normalize_setups(raw)
                    if not strict_mode or val == "":
                        return val
                    if not allowed_setup:
                        return val
                    parts = [p.strip() for p in val.split("|") if p.strip()]
                    norm_parts: list[str] = []
                    for part in parts:
                        key = part.lower()
                        if key not in allowed_setup:
                            raise ValueError(f"invalid setup: {part}")
                        norm_parts.append(allowed_setup[key])
                    out: list[str] = []
                    seen: set[str] = set()
                    for item in norm_parts:
                        k = item.lower()
                        if k in seen:
                            continue
                        seen.add(k)
                        out.append(item)
                    return " | ".join(out)

                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    trade_id = str(row.get("trade_id", "")).strip()
                    trade_day = str(row.get("TradeDay", "")).strip()
                    contract = str(row.get("ContractName", "")).strip()
                    intraday_idx = str(row.get("IntradayIndex", "")).strip()
                    setups = _normalize_setups_by_taxonomy(row.get("setups", row.get("Setup", "")))
                    phase = _normalize_by_taxonomy(row.get("phase", row.get("Phase", "")), allowed_phase, "Phase")
                    context = _normalize_by_taxonomy(row.get("context", row.get("Context", "")), allowed_context, "Context")
                    signal_bar = _normalize_by_taxonomy(row.get("signal_bar", row.get("SignalBar", "")), allowed_signal, "SignalBar")
                    trade_intent = _normalize_by_taxonomy(row.get("trade_intent", row.get("TradeIntent", "")), allowed_intent, "TradeIntent")
                    if not trade_id and (not trade_day or not contract or not intraday_idx):
                        continue

                    key_df = pd.DataFrame(
                        [
                            {
                                "trade_id": trade_id,
                                "TradeDay": trade_day,
                                "ContractName": contract,
                                "IntradayIndex": intraday_idx,
                            }
                        ]
                    )
                    key_df["trade_id"] = key_df["trade_id"].fillna("").astype(str).str.strip()
                    key_df["TradeDay"] = key_df["TradeDay"].astype(str).str.strip()
                    key_df["ContractName"] = key_df["ContractName"].astype(str).str.strip()
                    key_df["IntradayIndex"] = pd.to_numeric(key_df["IntradayIndex"], errors="coerce").fillna(-1).astype(int).astype(str)
                    eff_key = _effective_key(key_df).iloc[0]

                    mask = perf_df["__effective_key"] == eff_key
                    if mask.any():
                        perf_df.loc[mask, "Setup"] = setups
                        if phase or ("Phase" in row):
                            perf_df.loc[mask, "Phase"] = phase
                        if context or ("Context" in row):
                            perf_df.loc[mask, "Context"] = context
                        if signal_bar or ("SignalBar" in row):
                            perf_df.loc[mask, "SignalBar"] = signal_bar
                        if trade_intent or ("TradeIntent" in row):
                            perf_df.loc[mask, "TradeIntent"] = trade_intent
                        updated += 1
                        changed_keys.append(eff_key)
                    else:
                        skipped += 1

                perf_df = perf_df.drop(columns=["__effective_key"], errors="ignore")
                atomic_write_csv(perf_df, PERFORMANCE_CSV)
                append_audit_event(
                    "journal_tags_updated",
                    {
                        "performance_csv": PERFORMANCE_CSV,
                        "rows_requested": len(rows),
                        "updated": updated,
                        "inserted": 0,
                        "skipped": skipped,
                        "effective_keys": changed_keys[:200],
                    },
                    actor="api:/journal/tags",
                )
            return jsonify({"ok": True, "updated": updated, "inserted": 0, "skipped": skipped}), 200

        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"journal setup-tag update failed: {exc}"}), 500

    @api.route("/day-plan", methods=["GET", "POST", "OPTIONS"])
    def day_plan():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            if request.method == "GET":
                start = request.args.get("start")
                end = request.args.get("end")
                return jsonify({"rows": list_day_plan(start=start, end=end)}), 200

            payload = _require_json_object()
            rows = payload.get("rows")
            out = upsert_day_plan_rows(rows)
            return jsonify({"ok": True, **out}), 200
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"day plan update failed: {exc}"}), 500

    @api.route("/journal/live/meta", methods=["GET", "OPTIONS"])
    def journal_live_meta():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        contracts: list[dict[str, Any]] = []
        try:
            specs = pd.read_csv(CONTRACT_SPECS_CSV)
            if {"symbol", "point_value"}.issubset(set(specs.columns)):
                for _, row in specs.iterrows():
                    symbol = str(row.get("symbol", "")).strip()
                    pv = pd.to_numeric(row.get("point_value"), errors="coerce")
                    if symbol and pd.notna(pv):
                        contracts.append({"symbol": symbol, "point_value": float(pv)})
        except Exception:
            contracts = []
        taxonomy = taxonomy_payload()
        return (
            jsonify(
                {
                    "phase": taxonomy.get("phase", []),
                    "context": taxonomy.get("context", []),
                    "setup": taxonomy.get("setup", []),
                    "signal_bar": taxonomy.get("signal_bar", []),
                    "trade_intent": taxonomy.get("trade_intent", []),
                    "direction": [{"value": x} for x in sorted(DIRECTION_VALUES)],
                    "contracts": contracts,
                }
            ),
            200,
        )

    @api.route("/journal/live", methods=["GET", "POST", "OPTIONS"])
    def journal_live():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            if request.method == "GET":
                start = request.args.get("start")
                end = request.args.get("end")
                return jsonify({"rows": list_live_journal(start=start, end=end)}), 200

            payload = _require_json_object()
            rows = payload.get("rows")
            if not isinstance(rows, list):
                raise ValueError("rows must be an array")

            strict_mode = bool(get_app_config().get("tagging", {}).get("strict_mode", True))
            taxonomy = taxonomy_payload()
            allowed_phase = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("phase", [])}
            allowed_context = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("context", [])}
            allowed_setup = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("setup", [])}
            allowed_signal = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("signal_bar", [])}
            allowed_intent = {str(x.get("value", "")).strip().lower(): str(x.get("value", "")).strip() for x in taxonomy.get("trade_intent", [])}

            def _norm_tax(val: object, allowed_map: Dict[str, str], field: str) -> str:
                v = str(val or "").strip()
                if not strict_mode or v == "" or not allowed_map:
                    return v
                key = v.lower()
                if key not in allowed_map:
                    raise ValueError(f"invalid {field}: {v}")
                return allowed_map[key]

            normalized_rows: list[Dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                next_row = dict(row)
                next_row["Phase"] = _norm_tax(row.get("Phase"), allowed_phase, "Phase")
                next_row["Context"] = _norm_tax(row.get("Context"), allowed_context, "Context")
                next_row["SignalBar"] = _norm_tax(row.get("SignalBar"), allowed_signal, "SignalBar")
                next_row["TradeIntent"] = _norm_tax(row.get("TradeIntent"), allowed_intent, "TradeIntent")
                setup = str(row.get("Setup", "")).strip()
                if setup and strict_mode and allowed_setup:
                    parts = [p.strip() for p in setup.replace(";", "|").replace(",", "|").split("|") if p.strip()]
                    for part in parts:
                        if part.lower() not in allowed_setup:
                            raise ValueError(f"invalid Setup: {part}")
                    next_row["Setup"] = " | ".join(dict.fromkeys([allowed_setup[p.lower()] for p in parts]))
                normalized_rows.append(next_row)

            out = upsert_live_journal_rows(normalized_rows, actor="api:/journal/live")
            return jsonify({"ok": True, **out}), 200
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"live journal update failed: {exc}"}), 500

    @api.route("/journal/matching/parse-preview", methods=["POST", "OPTIONS"])
    def journal_matching_parse_preview():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            files = request.files.getlist("files")
            if not files:
                single = request.files.get("file")
                if single is not None:
                    files = [single]
            if not files:
                raise ValueError("no CSV files uploaded")

            raw_archive = str(request.form.get("archive_raw", "false")).strip().lower()
            archive_raw = raw_archive in {"1", "true", "yes", "y", "on"}

            saved_paths: list[str] = []
            parse_logs: list[dict[str, Any]] = []
            unparseable_rows: list[dict[str, Any]] = []
            parsed_frames: list[pd.DataFrame] = []

            Path(TEMP_PERF_DIR).mkdir(parents=True, exist_ok=True)
            stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            for idx, f in enumerate(files):
                if f is None:
                    continue
                raw_name = str(getattr(f, "filename", "") or "").strip()
                if not raw_name:
                    continue
                safe_name = os.path.basename(raw_name).replace(" ", "_")
                if not safe_name.lower().endswith(".csv"):
                    raise ValueError(f"only CSV files are allowed: {raw_name}")
                target = Path(TEMP_PERF_DIR) / f"preview_{stamp}_{idx}_{safe_name}"
                f.save(str(target))
                saved_paths.append(str(target))

                # Parse diagnostics first from raw rows.
                try:
                    raw_df = pd.read_csv(target)
                    required = {"Date/Time", "Symbol", "Quantity"}
                    missing = sorted(list(required.difference(set(raw_df.columns))))
                    if missing:
                        unparseable_rows.append(
                            {
                                "file": safe_name,
                                "row_number": None,
                                "reason": f"missing required columns: {', '.join(missing)}",
                                "row": {},
                            }
                        )
                        parse_logs.append({"file": safe_name, "status": "failed", "parsed_rows": 0, "reason": "missing_columns"})
                        continue

                    qty = pd.to_numeric(raw_df["Quantity"], errors="coerce").fillna(0.0)
                    raw_df["__qty"] = qty
                    by_symbol = raw_df.groupby(raw_df["Symbol"].astype(str), observed=True)["__qty"].sum()
                    bad_symbols = by_symbol[by_symbol != 0]
                    if not bad_symbols.empty:
                        for symbol, net_qty in bad_symbols.items():
                            bad_rows = raw_df[raw_df["Symbol"].astype(str) == str(symbol)].copy()
                            for ridx, row in bad_rows.iterrows():
                                unparseable_rows.append(
                                    {
                                        "file": safe_name,
                                        "row_number": int(ridx) + 2,  # CSV header offset
                                        "reason": f"symbol net quantity is not zero ({net_qty}); incomplete round-trip set",
                                        "row": {k: (None if pd.isna(v) else str(v)) for k, v in row.to_dict().items() if not str(k).startswith("__")},
                                    }
                                )
                        parse_logs.append(
                            {
                                "file": safe_name,
                                "status": "failed",
                                "parsed_rows": 0,
                                "reason": "net_quantity_not_zero",
                                "bad_symbols": [{"symbol": str(k), "net_qty": float(v)} for k, v in bad_symbols.items()],
                            }
                        )
                        continue
                except Exception as exc:
                    unparseable_rows.append(
                        {
                            "file": safe_name,
                            "row_number": None,
                            "reason": f"failed to read raw csv: {exc}",
                            "row": {},
                        }
                    )
                    parse_logs.append({"file": safe_name, "status": "failed", "parsed_rows": 0, "reason": "read_error"})
                    continue

                # Convert raw fills to round-trip trades (preview only).
                try:
                    parsed_df = process_csv(str(target))
                    if parsed_df.empty:
                        unparseable_rows.append(
                            {
                                "file": safe_name,
                                "row_number": None,
                                "reason": "no round-trip trades parsed from file",
                                "row": {},
                            }
                        )
                        parse_logs.append({"file": safe_name, "status": "failed", "parsed_rows": 0, "reason": "empty_parse"})
                        continue
                    parsed_frames.append(parsed_df)
                    parse_logs.append({"file": safe_name, "status": "ok", "parsed_rows": int(len(parsed_df))})
                except Exception as exc:
                    unparseable_rows.append(
                        {
                            "file": safe_name,
                            "row_number": None,
                            "reason": f"parse error: {exc}",
                            "row": {},
                        }
                    )
                    parse_logs.append({"file": safe_name, "status": "failed", "parsed_rows": 0, "reason": "parse_error"})

            # cleanup/archive raw uploads from preview stage
            archived_files: list[str] = []
            removed_files: list[str] = []
            archive_dir = Path(TEMP_PERF_DIR) / "archive"
            if archive_raw:
                archive_dir.mkdir(parents=True, exist_ok=True)
            for p in saved_paths:
                pp = Path(p)
                if not pp.exists():
                    continue
                try:
                    if archive_raw:
                        dst = archive_dir / pp.name
                        pp.replace(dst)
                        archived_files.append(str(dst))
                    else:
                        pp.unlink()
                        removed_files.append(str(pp))
                except OSError:
                    pass

            parsed_trades: list[dict[str, Any]] = []
            if parsed_frames:
                combined = pd.concat(parsed_frames, ignore_index=True)
                combined = ensure_trade_id(combined)
                for _, row in combined.iterrows():
                    rec = row.to_dict()
                    rec["preview_trade_id"] = str(rec.get("trade_id", ""))
                    parsed_trades.append({k: (None if pd.isna(v) else v) for k, v in rec.items()})

            parsed_days = sorted(
                {
                    str(r.get("TradeDay", "")).strip()
                    for r in parsed_trades
                    if str(r.get("TradeDay", "")).strip() != ""
                }
            )
            range_start = parsed_days[0] if parsed_days else ""
            range_end = parsed_days[-1] if parsed_days else ""
            journal_rows = list_live_journal(start=range_start or None, end=range_end or None) if parsed_days else []

            suggestions: list[dict[str, Any]] = []
            if parsed_days and journal_rows and parsed_trades:
                trades_by_day: dict[str, list[dict[str, Any]]] = {}
                for t in parsed_trades:
                    d = str(t.get("TradeDay", "")).strip()
                    if not d:
                        continue
                    trades_by_day.setdefault(d, []).append(t)
                journals_by_day: dict[str, list[dict[str, Any]]] = {}
                for j in journal_rows:
                    d = str(j.get("TradeDay", "")).strip()
                    if not d:
                        continue
                    journals_by_day.setdefault(d, []).append(j)
                for day in sorted(set(trades_by_day.keys()).intersection(set(journals_by_day.keys()))):
                    jrows = sorted(journals_by_day[day], key=lambda x: int(pd.to_numeric(x.get("SeqInDay"), errors="coerce") or 0))
                    prows = sorted(trades_by_day[day], key=lambda x: (str(x.get("EnteredAt", "")), str(x.get("preview_trade_id", ""))))
                    for j_idx, j in enumerate(jrows):
                        best: list[dict[str, Any]] = []
                        for p_idx, p in enumerate(prows):
                            pair = _pair_match_tiered(j, p, p_idx, j_idx)
                            best.append(
                                {
                                    "trade_day": day,
                                    "journal_id": str(j.get("journal_id", "")),
                                    "preview_trade_id": str(p.get("preview_trade_id", "")),
                                    "score": pair["score"],
                                    "match_type": pair["match_type"],
                                    "tier": pair["tier"],
                                    "hard_conflict": pair["hard_conflict"],
                                    "reasons": pair["reasons"],
                                }
                            )
                        ranked = sorted(
                            best,
                            key=lambda x: (int(x.get("tier", 9)), -float(x.get("score", -1e9)), bool(x.get("hard_conflict", False))),
                        )[:5]
                        if ranked:
                            ranked[0]["recommended"] = True
                        suggestions.extend(ranked)

            can_continue = bool(parsed_trades) and (len(unparseable_rows) == 0)
            return (
                jsonify(
                    {
                        "ok": True,
                        "can_continue": can_continue,
                        "hard_blocked": not can_continue,
                        "saved_files": saved_paths,
                        "archived_files": archived_files,
                        "removed_files": removed_files,
                        "parse_logs": parse_logs,
                        "unparseable_rows": unparseable_rows,
                        "parsed_trades": parsed_trades,
                        "parsed_range": {"start": range_start, "end": range_end, "days": parsed_days},
                        "journal_rows": journal_rows,
                        "suggestions": suggestions,
                    }
                ),
                200,
            )
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"parse preview failed: {exc}"}), 500

    @api.route("/journal/matching/commit", methods=["POST", "OPTIONS"])
    def journal_matching_commit():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            payload = _require_json_object()
            parsed_trades = payload.get("parsed_trades")
            links = payload.get("links", [])
            replace_for_journal = bool(payload.get("replace_for_journal", True))
            if not isinstance(parsed_trades, list) or not parsed_trades:
                raise ValueError("parsed_trades must be a non-empty array")
            if not isinstance(links, list):
                raise ValueError("links must be an array")

            incoming_df = pd.DataFrame(parsed_trades)
            required_cols = ["ContractName", "EnteredAt", "ExitedAt", "EntryPrice", "ExitPrice", "Fees", "PnL", "Size", "Type", "TradeDay", "TradeDuration"]
            missing = [c for c in required_cols if c not in incoming_df.columns]
            if missing:
                raise ValueError(f"parsed_trades missing required columns: {', '.join(missing)}")

            preview_id_col = "preview_trade_id" if "preview_trade_id" in incoming_df.columns else ("trade_id" if "trade_id" in incoming_df.columns else "")
            if not preview_id_col:
                raise ValueError("parsed_trades must include preview_trade_id or trade_id")

            id_df = ensure_trade_id(incoming_df.copy())
            preview_to_trade_id = {
                str(row.get(preview_id_col, "")).strip(): str(row.get("trade_id", "")).strip()
                for _, row in id_df.iterrows()
                if str(row.get(preview_id_col, "")).strip()
            }
            trade_id_to_day = {
                str(row.get("trade_id", "")).strip(): str(row.get("TradeDay", "")).strip()
                for _, row in id_df.iterrows()
                if str(row.get("trade_id", "")).strip()
            }

            pre_rows = 0
            if os.path.exists(PERFORMANCE_CSV):
                try:
                    pre_rows = int(len(pd.read_csv(PERFORMANCE_CSV)))
                except Exception:
                    pre_rows = 0

            merged_df = generate_aggregated_data([incoming_df[required_cols].copy()])
            post_rows = int(len(merged_df))

            inserted_matches = 0
            inactivated_matches = 0
            links_by_day: dict[str, list[dict[str, Any]]] = {}
            for raw in links:
                if not isinstance(raw, dict):
                    continue
                journal_id = str(raw.get("journal_id", "")).strip()
                preview_trade_id = str(raw.get("preview_trade_id", raw.get("trade_id", ""))).strip()
                if not journal_id or not preview_trade_id:
                    continue
                trade_id = preview_to_trade_id.get(preview_trade_id, "")
                if not trade_id:
                    raise ValueError(f"preview trade id not found in parsed set: {preview_trade_id}")
                day = trade_id_to_day.get(trade_id, "")
                if not day:
                    raise ValueError(f"trade day missing for trade id: {trade_id}")
                links_by_day.setdefault(day, []).append(
                    {
                        "journal_id": journal_id,
                        "trade_id": trade_id,
                        "score": raw.get("score", 0),
                        "match_type": raw.get("match_type", "manual"),
                        "is_primary": bool(raw.get("is_primary", True)),
                    }
                )

            for day, day_links in links_by_day.items():
                out = confirm_matches(
                    day,
                    day_links,
                    replace_for_journal=replace_for_journal,
                    actor="api:/journal/matching/commit",
                )
                inserted_matches += int(out.get("inserted", 0))
                inactivated_matches += int(out.get("inactivated", 0))

            return (
                jsonify(
                    {
                        "ok": True,
                        "merged": True,
                        "rows_before": pre_rows,
                        "rows_after": post_rows,
                        "rows_delta": post_rows - pre_rows,
                        "matches_inserted": inserted_matches,
                        "matches_inactivated": inactivated_matches,
                    }
                ),
                200,
            )
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"matching commit failed: {exc}"}), 500

    @api.route("/journal/matching/links", methods=["GET", "OPTIONS"])
    def journal_matching_links():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            start = request.args.get("start")
            end = request.args.get("end")
            rows = list_active_matches(start=start, end=end)

            journal = load_journal_live()
            jmap = {}
            if not journal.empty:
                for _, r in journal.iterrows():
                    jmap[str(r.get("journal_id", ""))] = {
                        "journal_id": str(r.get("journal_id", "")),
                        "TradeDay": str(r.get("TradeDay", "")),
                        "SeqInDay": str(r.get("SeqInDay", "")),
                        "ContractName": str(r.get("ContractName", "")),
                        "Direction": str(r.get("Direction", "")),
                        "Size": str(r.get("Size", "")),
                        "TradeIntent": str(r.get("TradeIntent", "")),
                    }

            tmap: dict[str, dict[str, Any]] = {}
            if os.path.exists(PERFORMANCE_CSV):
                try:
                    perf = ensure_trade_id(pd.read_csv(PERFORMANCE_CSV))
                    for _, r in perf.iterrows():
                        tid = str(r.get("trade_id", "")).strip()
                        if not tid:
                            continue
                        tmap[tid] = {
                            "trade_id": tid,
                            "TradeDay": str(r.get("TradeDay", "")),
                            "ContractName": str(r.get("ContractName", "")),
                            "Type": str(r.get("Type", "")),
                            "Size": str(r.get("Size", "")),
                            "EntryPrice": str(r.get("EntryPrice", "")),
                            "ExitPrice": str(r.get("ExitPrice", "")),
                        }
                except Exception:
                    tmap = {}

            out = []
            for r in rows:
                jid = str(r.get("journal_id", ""))
                tid = str(r.get("trade_id", ""))
                out.append(
                    {
                        **r,
                        "journal": jmap.get(jid, {}),
                        "trade": tmap.get(tid, {}),
                    }
                )
            return jsonify({"ok": True, "rows": out}), 200
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"matching links load failed: {exc}"}), 500

    @api.route("/journal/matching/unlink", methods=["POST", "OPTIONS"])
    def journal_matching_unlink():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        try:
            payload = _require_json_object()
            journal_id = payload.get("journal_id")
            trade_id = payload.get("trade_id")
            trade_day = payload.get("trade_day")
            out = unlink_matches(
                str(journal_id or ""),
                trade_id=str(trade_id or ""),
                trade_day=str(trade_day or ""),
                actor="api:/journal/matching/unlink",
            )
            return jsonify({"ok": True, **out}), 200
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"matching unlink failed: {exc}"}), 500

    @api.route("/trading/session", methods=["GET", "OPTIONS"])
    def trading_session():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)

        try:
            symbol = _validate_symbol(request.args.get("symbol"), required=True)
            if symbol is None:
                return jsonify({"error": "symbol is required"}), 400
            start_raw = request.args.get("start")
            end_raw = request.args.get("end")
            _parse_range(start_raw, end_raw, normalize_date=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        csv_path = DATA_SOURCE_DROPDOWN.get(symbol)
        if not os.path.exists(PERFORMANCE_CSV):
            return jsonify({"error": "performance data not found"}), 404
        try:
            default_start = "1900-01-01"
            default_end = "2100-01-01"
            perf_df = merge_trade_labels(ensure_trade_id(load_performance(symbol, start_raw or default_start, end_raw or default_end, PERFORMANCE_CSV)))
            fut_df = load_future(start_raw or default_start, end_raw or default_end, csv_path)

            # Stats from plots helper
            stats = get_statistics(perf_df.copy()) if not perf_df.empty else {}
            stats_payload = {
                "win_loss": stats.get("win_loss_data", []),
                "financial_metrics": stats.get("financial_metrics", {}),
                "win_loss_by_type": stats.get("win_loss_by_type", []),
                "streak_data": stats.get("streak_data", pd.DataFrame()).to_dict("records")
                if isinstance(stats.get("streak_data"), pd.DataFrame)
                else [],
                "duration_data": stats.get("duration_data", pd.Series([])).tolist()
                if hasattr(stats.get("duration_data", None), "tolist")
                else [],
                "size_counts": stats.get("size_counts", pd.DataFrame()).to_dict("records")
                if isinstance(stats.get("size_counts"), pd.DataFrame)
                else [],
            }

            # Normalize future bars to ISO
            future_records = []
            for _, row in fut_df.iterrows():
                future_records.append(
                    {
                        "time": _iso_in_timezone(row["Datetime"], ANALYSIS_TIMEZONE),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row["Volume"]) if "Volume" in row else None,
                    }
                )

            perf_payload = perf_df.copy()
            for col in ["EnteredAt", "ExitedAt"]:
                if col in perf_payload.columns:
                    perf_payload[col] = perf_payload[col].apply(lambda v: _iso_in_timezone(v, ANALYSIS_TIMEZONE))
            perf_records = perf_payload.replace({np.nan: None}).to_dict("records")
            return jsonify({"future": future_records, "performance": perf_records, "stats": stats_payload})
        except (FileNotFoundError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except (KeyError, TypeError, pd.errors.ParserError, OSError) as exc:
            return jsonify({"error": f"failed to load session: {exc}"}), 500

    # Register blueprint after all routes are declared
    server.register_blueprint(api)
