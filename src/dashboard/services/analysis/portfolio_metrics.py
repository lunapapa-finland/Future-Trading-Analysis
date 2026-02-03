from __future__ import annotations

import pandas as pd
import math
from dashboard.services.portfolio import PORTFOLIO_CSV, _read_rows  # type: ignore
from dashboard.config.analysis import RISK_FREE_RATE, INITIAL_NET_LIQ, PORTFOLIO_START_DATE


def load_portfolio_df() -> pd.DataFrame:
    rows = _read_rows()
    if not rows:
        return pd.DataFrame(columns=["date", "equity", "pnl", "reason"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["equity"] = pd.to_numeric(df["equity"], errors="coerce")
    df["pnl"] = pd.to_numeric(df.get("pnl", 0), errors="coerce")
    df = df.dropna(subset=["date", "equity"])
    df = df.sort_values("date")
    return df


def portfolio_metrics():
    df = load_portfolio_df()
    if df.empty:
        return {
            "latest_equity": float(INITIAL_NET_LIQ),
            "max_drawdown": None,
            "cagr": None,
            "sharpe": None,
        }
    df["return"] = df["equity"].pct_change().fillna(0)
    latest_equity = df["equity"].iloc[-1]

    # max drawdown
    roll_max = df["equity"].cummax()
    drawdowns = (df["equity"] - roll_max) / roll_max.replace(0, pd.NA)
    max_drawdown = drawdowns.min()

    # CAGR (based on first/last equity and elapsed years)
    days = (df["date"].iloc[-1] - df["date"].iloc[0]).days or 1
    years = days / 365.0
    cagr = (df["equity"].iloc[-1] / df["equity"].iloc[0]) ** (1 / years) - 1 if df["equity"].iloc[0] > 0 else None

    # Sharpe using daily returns vs risk-free
    rf_daily = RISK_FREE_RATE / 365.0
    excess = df["return"] - rf_daily
    mean_excess = excess.mean()
    std_excess = excess.std(ddof=1) or math.nan
    sharpe = (mean_excess * math.sqrt(252)) / std_excess if std_excess and not math.isnan(std_excess) else None

    return {
        "latest_equity": float(latest_equity),
        "max_drawdown": float(max_drawdown) if max_drawdown is not None else None,
        "cagr": float(cagr) if cagr is not None else None,
        "sharpe": float(sharpe) if sharpe is not None else None,
    }
