import pandas as pd

from dashboard.services.analysis import compute
from dashboard.services.analysis.behavioral import behavior_heatmap


def _fixture_df() -> pd.DataFrame:
    entered = pd.to_datetime(
        [
            "2025-01-06 09:00:00Z",  # Monday
            "2025-01-07 10:00:00Z",  # Tuesday
            "2025-01-08 09:00:00Z",  # Wednesday
            "2025-01-09 10:00:00Z",  # Thursday
            "2025-01-10 09:00:00Z",  # Friday
            "2025-01-13 10:00:00Z",  # Monday
        ],
        utc=True,
    )
    exited = pd.to_datetime(
        [
            "2025-01-06 10:00:00Z",
            "2025-01-07 11:00:00Z",
            "2025-01-08 10:00:00Z",
            "2025-01-09 11:00:00Z",
            "2025-01-10 10:00:00Z",
            "2025-01-13 11:00:00Z",
        ],
        utc=True,
    )
    return pd.DataFrame(
        {
            "EnteredAt": entered,
            "ExitedAt": exited,
            "PnL(Net)": [100, -50, 200, -100, 50, -25],
            "HourOfDay": [9, 10, 9, 10, 9, 10],
        }
    )


def test_rolling_win_rate_regression():
    df = _fixture_df()
    out = compute.rolling_win_rate(df, window=3)
    assert out["TradeIndex"].tolist() == [2, 3, 4, 5]
    assert out["WinRate"].tolist() == [66.67, 33.33, 66.67, 33.33]


def test_drawdown_regression():
    df = _fixture_df()
    out = compute.drawdown(df, granularity="1D")
    assert out["Drawdown"].tolist() == [0, -50, 0, -100, -50, -75]


def test_sharpe_ratio_regression():
    df = _fixture_df()
    out = compute.sharpe_ratio(df, window=3, risk_free_rate=0.0, initial_capital=10000)
    assert out["SharpeRatio"].tolist() == [10.55, 1.73, 5.38, -5.25]


def test_behavioral_heatmap_regression():
    df = _fixture_df()
    out = behavior_heatmap(df)

    # 24 hours x 5 weekdays matrix
    assert len(out) == 120

    monday_9 = out[(out["DayOfWeek"] == "Monday") & (out["HourOfDay"] == 9)]["PnL(Net)"].iloc[0]
    monday_10 = out[(out["DayOfWeek"] == "Monday") & (out["HourOfDay"] == 10)]["PnL(Net)"].iloc[0]
    tuesday_10 = out[(out["DayOfWeek"] == "Tuesday") & (out["HourOfDay"] == 10)]["PnL(Net)"].iloc[0]
    friday_9 = out[(out["DayOfWeek"] == "Friday") & (out["HourOfDay"] == 9)]["PnL(Net)"].iloc[0]

    assert monday_9 == 100
    assert monday_10 == -25
    assert tuesday_10 == -50
    assert friday_9 == 50
