from __future__ import annotations

import pandas as pd
import numpy as np
from dashboard.services.analysis.schema import validate_performance_df


def behavior_heatmap(performance_df: pd.DataFrame) -> pd.DataFrame:
    df = validate_performance_df(performance_df)
    if "HourOfDay" not in df.columns or "PnL(Net)" not in df.columns:
        raise ValueError("HourOfDay and PnL(Net) required")
    df["HourOfDay"] = df["HourOfDay"].astype(int)
    df["DayOfWeek"] = pd.to_datetime(df["EnteredAt"]).dt.day_name()
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    grouped = df.groupby(["HourOfDay", "DayOfWeek"], observed=True)["PnL(Net)"].sum().reset_index()
    grouped["DayOfWeek"] = pd.Categorical(grouped["DayOfWeek"], categories=weekday_order, ordered=True)
    all_hours = np.arange(0, 24)
    full_index = pd.MultiIndex.from_product([all_hours, weekday_order], names=["HourOfDay", "DayOfWeek"])
    full_df = pd.DataFrame(index=full_index).reset_index()
    merged = full_df.merge(grouped, on=["HourOfDay", "DayOfWeek"], how="left").fillna({"PnL(Net)": 0})
    return merged
