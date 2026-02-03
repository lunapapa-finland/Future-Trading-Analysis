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
from dashboard.config.settings import DATA_SOURCE_DROPDOWN, PERFORMANCE_CSV, SYMBOL_ASSET_CLASS, SYMBOL_CATALOG
from dashboard.config.env import TIMEFRAME_OPTIONS, PLAYBACK_SPEEDS
from dashboard.config.analysis import RISK_FREE_RATE, INITIAL_NET_LIQ, PORTFOLIO_START_DATE
from dashboard.services.data.load_data import load_performance, load_future
from dashboard.services.portfolio import latest_equity, equity_series, append_manual
from dashboard.services.analysis.portfolio_metrics import portfolio_metrics
import numpy as np


def _iso(dt: pd.Timestamp) -> str:
    if pd.isna(dt):
        return ""
    if dt.tzinfo:
        return dt.isoformat()
    return dt.tz_localize("UTC").isoformat()


def _parse_date(val: Optional[str]) -> Optional[pd.Timestamp]:
    if not val:
        return None
    try:
        ts = pd.to_datetime(val)
        # Ensure tz-aware (default to UTC for naive inputs)
        if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return ts
    except Exception:
        return None


def _cors_headers(response, allowed_origin: str):
    response.headers["Access-Control-Allow-Origin"] = allowed_origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


def register_api(server):
    allowed_origin = os.environ.get("FRONTEND_ORIGIN", "*")
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
            }
        )

    @api.route("/portfolio", methods=["GET"])
    def portfolio():
        try:
            latest = latest_equity()
            series = equity_series(limit=500)
            metrics = portfolio_metrics()
            return jsonify({"latest": latest, "series": series, "risk_free_rate": RISK_FREE_RATE, "metrics": metrics})
        except Exception as exc:
            return jsonify({"error": f"failed to load portfolio: {exc}"}), 500

    @api.route("/portfolio/adjust", methods=["POST"])
    def portfolio_adjust():
        payload = request.get_json() or {}
        reason = payload.get("reason", "").lower()
        try:
            amount = float(payload.get("amount", 0))
        except Exception:
            return jsonify({"error": "amount must be a number"}), 400
        if amount <= 0:
            return jsonify({"error": "amount must be positive"}), 400
        date_str = payload.get("date")
        if reason not in {"deposit", "withdraw"}:
            return jsonify({"error": "reason must be deposit or withdraw"}), 400
        if date_str:
            try:
                datetime.fromisoformat(date_str)
            except Exception:
                return jsonify({"error": "date must be ISO format YYYY-MM-DD"}), 400
        if reason == "withdraw":
            amount = -abs(amount)
        else:
            amount = abs(amount)
        try:
            entry = append_manual(reason=reason, amount=amount, date_override=date_str)
            return jsonify({"ok": True, "entry": entry})
        except Exception as e:
            return jsonify({"error": f"failed to append: {e}"}), 500

    @api.route("/candles", methods=["GET", "OPTIONS"])
    def candles():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)

        symbol = request.args.get("symbol")
        if not symbol:
            return jsonify({"error": "symbol is required"}), 400
        csv_path = DATA_SOURCE_DROPDOWN.get(symbol)
        if not csv_path:
            return jsonify({"error": f"unknown symbol {symbol}"}), 404
        if not os.path.exists(csv_path):
            return jsonify({"error": f"data not found for {symbol}"}), 404

        start = _parse_date(request.args.get("start"))
        end = _parse_date(request.args.get("end"))

        try:
            df = pd.read_csv(csv_path, parse_dates=["Datetime"])
            # Normalize to UTC for consistent comparisons
            df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True, errors="coerce")
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
                        "time": _iso(row["Datetime"]),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row["Volume"]) if has_volume else None,
                    }
                )
            return jsonify(records)
        except Exception as exc:  # pragma: no cover - minimal error handling
            return jsonify({"error": f"failed to read candles: {exc}"}), 500

    @api.route("/performance/combined", methods=["GET", "OPTIONS"])
    def combined_performance():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)
        if not os.path.exists(PERFORMANCE_CSV):
            return jsonify({"error": "performance data not found"}), 404
        start = _parse_date(request.args.get("start"))
        end = _parse_date(request.args.get("end"))
        try:
            df = pd.read_csv(PERFORMANCE_CSV)
            if start or end:
                if "TradeDay" in df.columns:
                    df["TradeDay"] = pd.to_datetime(df["TradeDay"], utc=True, errors="coerce")
                    if start:
                        df = df[df["TradeDay"] >= start]
                    if end:
                        df = df[df["TradeDay"] <= end]
                elif "ExitedAt" in df.columns:
                    df["ExitedAt"] = pd.to_datetime(df["ExitedAt"], utc=True, errors="coerce")
                    if start:
                        df = df[df["ExitedAt"] >= start]
                    if end:
                        df = df[df["ExitedAt"] <= end]
            records = df.to_dict(orient="records")
            return jsonify(records)
        except Exception as exc:
            return jsonify({"error": f"failed to read performance: {exc}"}), 500

    def _load_performance_df(payload: Dict[str, Any]) -> pd.DataFrame:
        if not os.path.exists(PERFORMANCE_CSV):
            raise FileNotFoundError("performance data not found")
        df = pd.read_csv(PERFORMANCE_CSV)
        start = _parse_date(payload.get("start_date"))
        end = _parse_date(payload.get("end_date"))
        if start or end:
            if "TradeDay" in df.columns:
                df["TradeDay"] = pd.to_datetime(df["TradeDay"], utc=True, errors="coerce")
                if start:
                    df = df[df["TradeDay"] >= start]
                if end:
                    df = df[df["TradeDay"] <= end]
            elif "ExitedAt" in df.columns:
                df["ExitedAt"] = pd.to_datetime(df["ExitedAt"], utc=True, errors="coerce")
                if start:
                    df = df[df["ExitedAt"] >= start]
                if end:
                    df = df[df["ExitedAt"] <= end]
        return df

    def _to_records(df: pd.DataFrame) -> list[Dict[str, Any]]:
        return df.to_dict(orient="records")

    def _metric_handler(metric: str, df: pd.DataFrame, payload: Dict[str, Any]) -> Tuple[Any, int]:
        granularity = payload.get("granularity")
        window = payload.get("window")
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
            out = compute.rolling_win_rate(df, window=window or compute.DEFAULT_ROLLING_WINDOW)
            return _to_records(out), 200
        elif metric == "sharpe_ratio":
            out = compute.sharpe_ratio(
                df, window=window or compute.DEFAULT_ROLLING_WINDOW, risk_free_rate=params.get("risk_free_rate", 0.02)
            )
            return _to_records(out), 200
        elif metric == "trade_efficiency":
            out = compute.trade_efficiency(df, window=window or compute.DEFAULT_ROLLING_WINDOW)
            return _to_records(out), 200
        elif metric == "hourly_performance":
            out = compute.hourly_performance(df, window=window or compute.DEFAULT_ROLLING_WINDOW)
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
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        try:
            df = _load_performance_df(payload)
            if df.empty:
                return jsonify({"error": "performance dataset is empty"}), 400
            body, status = _metric_handler(metric, df, payload)
            return jsonify(body), status
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": f"analysis failed: {exc}"}), 500

    @api.route("/trading/session", methods=["GET", "OPTIONS"])
    def trading_session():
        if request.method == "OPTIONS":
            return _cors_headers(jsonify({"ok": True}), allowed_origin)

        symbol = request.args.get("symbol")
        start_raw = request.args.get("start")
        end_raw = request.args.get("end")
        if not symbol:
            return jsonify({"error": "symbol is required"}), 400
        csv_path = DATA_SOURCE_DROPDOWN.get(symbol)
        if not csv_path:
            return jsonify({"error": f"unknown symbol {symbol}"}), 404
        if not os.path.exists(PERFORMANCE_CSV):
            return jsonify({"error": "performance data not found"}), 404
        try:
            default_start = "1900-01-01"
            default_end = "2100-01-01"
            perf_df = load_performance(symbol, start_raw or default_start, end_raw or default_end, PERFORMANCE_CSV)
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
                        "time": _iso(pd.to_datetime(row["Datetime"], utc=True)),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row["Volume"]) if "Volume" in row else None,
                    }
                )

            perf_records = perf_df.replace({np.nan: None}).to_dict("records")
            return jsonify({"future": future_records, "performance": perf_records, "stats": stats_payload})
        except Exception as exc:
            return jsonify({"error": f"failed to load session: {exc}"}), 500

    # Register blueprint after all routes are declared
    server.register_blueprint(api)
