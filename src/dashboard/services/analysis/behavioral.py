from __future__ import annotations

import pandas as pd
import numpy as np
from dashboard.services.analysis.schema import validate_performance_df
from dashboard.config.env import TIMEZONE


def behavior_heatmap(performance_df: pd.DataFrame) -> pd.DataFrame:
    df = validate_performance_df(performance_df)
    if "EnteredAt" not in df.columns or "PnL(Net)" not in df.columns:
        raise ValueError("EnteredAt and PnL(Net) required")
    entered = pd.to_datetime(df["EnteredAt"], utc=True, errors="coerce").dt.tz_convert(TIMEZONE)
    if entered.isna().any():
        raise ValueError("Invalid datetime values in 'EnteredAt' column")
    df["HourOfDay"] = entered.dt.hour.astype(int)
    df["DayOfWeek"] = entered.dt.day_name()
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    grouped = df.groupby(["HourOfDay", "DayOfWeek"], observed=True)["PnL(Net)"].sum().reset_index()
    grouped["DayOfWeek"] = pd.Categorical(grouped["DayOfWeek"], categories=weekday_order, ordered=True)
    all_hours = np.arange(0, 24)
    full_index = pd.MultiIndex.from_product([all_hours, weekday_order], names=["HourOfDay", "DayOfWeek"])
    full_df = pd.DataFrame(index=full_index).reset_index()
    merged = full_df.merge(grouped, on=["HourOfDay", "DayOfWeek"], how="left").fillna({"PnL(Net)": 0})
    return merged
