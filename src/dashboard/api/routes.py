"""
Lightweight JSON API shim exposing existing analytics for the new frontend.

Routes:
- GET /api/candles            -> raw 5m OHLCV from CSV
- GET /api/performance/combined -> combined performance CSV
- POST /api/analysis/<metric> -> wraps functions in dashboard.analysis.compute
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from flask import Blueprint, jsonify, request

from dashboard.services.analysis import compute
from dashboard.services.analysis.behavioral import behavior_heatmap
from dashboard.services.analysis.plots import get_statistics
from dashboard.config.settings import DATA_SOURCE_DROPDOWN, PERFORMANCE_CSV, SYMBOL_CATALOG
from dashboard.config.env import TIMEFRAME_OPTIONS, PLAYBACK_SPEEDS
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
    payload["symbol"] = _validate_symbol(payload.get("symbol"), required=False)
    start, end = _parse_range(payload.get("start_date"), payload.get("end_date"), normalize_date=True)
    payload["start_date"] = start
    payload["end_date"] = end
    return payload


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
