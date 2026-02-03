from __future__ import annotations

import pandas as pd


def validate_performance_df(df: pd.DataFrame) -> pd.DataFrame:
    required = ["EnteredAt", "ExitedAt", "PnL(Net)"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    df = df.copy()
    df["EnteredAt"] = pd.to_datetime(df["EnteredAt"], errors="coerce", utc=True)
    df["ExitedAt"] = pd.to_datetime(df["ExitedAt"], errors="coerce", utc=True)
    if df["EnteredAt"].isna().any() or df["ExitedAt"].isna().any():
        raise ValueError("Invalid datetimes in EnteredAt/ExitedAt")
    if df["PnL(Net)"].isna().any():
        df["PnL(Net)"] = df["PnL(Net)"].fillna(0)
    # Optional fields normalization
    if "TradeDay" in df.columns:
        df["TradeDay"] = pd.to_datetime(df["TradeDay"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    return df
