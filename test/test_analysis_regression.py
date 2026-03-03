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


def test_drawdown_first_period_loss_is_negative_from_zero_baseline():
    df = pd.DataFrame(
        {
            "EnteredAt": pd.to_datetime(
                ["2025-02-03 09:00:00Z", "2025-02-04 09:00:00Z"],
                utc=True,
            ),
            "ExitedAt": pd.to_datetime(
                ["2025-02-03 09:30:00Z", "2025-02-04 09:30:00Z"],
                utc=True,
            ),
            "PnL(Net)": [-100, 50],
        }
    )
    out = compute.drawdown(df, granularity="1D")
    assert out["Drawdown"].tolist() == [-100, -50]


def test_sharpe_ratio_regression():
    df = _fixture_df()
    out = compute.sharpe_ratio(df, window=3, risk_free_rate=0.0, initial_capital=10000)
    assert out["SharpeRatio"].tolist() == [10.55, 1.73, 5.38, -5.25]


def test_behavioral_heatmap_regression():
    df = _fixture_df()
    out = behavior_heatmap(df)

    # 24 hours x 7 weekdays matrix
    assert len(out) == 168

    # EnteredAt is normalized to CME (US/Central), so UTC 09/10 become CT 03/04 in January.
    monday_3 = out[(out["DayOfWeek"] == "Monday") & (out["HourOfDay"] == 3)]["PnL(Net)"].iloc[0]
    monday_4 = out[(out["DayOfWeek"] == "Monday") & (out["HourOfDay"] == 4)]["PnL(Net)"].iloc[0]
    tuesday_4 = out[(out["DayOfWeek"] == "Tuesday") & (out["HourOfDay"] == 4)]["PnL(Net)"].iloc[0]
    friday_3 = out[(out["DayOfWeek"] == "Friday") & (out["HourOfDay"] == 3)]["PnL(Net)"].iloc[0]

    assert monday_3 == 100
    assert monday_4 == -25
    assert tuesday_4 == -50
    assert friday_3 == 50


def test_pnl_growth_passive_curve_starts_at_zero():
    df = pd.DataFrame(
        {
            "EnteredAt": pd.to_datetime(["2025-01-01 09:00:00Z"], utc=True),
            "ExitedAt": pd.to_datetime(["2025-01-01 10:00:00Z"], utc=True),
            "PnL(Net)": [0],
        }
    )
    out = compute.pnl_growth(df, granularity="1D", daily_compounding_rate=0.01, initial_funding=10000)
    assert float(out.iloc[0]["PassiveGrowth"]) == 0.0
    assert float(out.iloc[0]["CumulativePassive"]) == 0.0


def test_hourly_performance_uses_enteredat_hour_buckets():
    df = pd.DataFrame(
        {
            "EnteredAt": pd.to_datetime(
                [
                    "2026-02-28 08:05:00Z",
                    "2026-02-28 08:40:00Z",
                    "2026-02-28 09:10:00Z",
                ],
                utc=True,
            ),
            "ExitedAt": pd.to_datetime(
                [
                    "2026-02-28 08:20:00Z",
                    "2026-02-28 08:50:00Z",
                    "2026-02-28 09:30:00Z",
                ],
                utc=True,
            ),
            "PnL(Net)": [10, 20, 30],
        }
    )
    out = compute.hourly_performance(df)
    # February timestamps are also interpreted in CME (CST), so UTC 08/09 become CT 02/03.
    assert out["HourOfDay"].tolist() == [2, 3]
    assert out["TradeCount"].tolist() == [2, 1]
    # statistical avg pnl per hour bucket across selected range
    assert out["HourlyPnL"].tolist() == [15.0, 30.0]


def test_overtrading_tags_all_post_loss_trades_in_window():
    df = pd.DataFrame(
        {
            "EnteredAt": pd.to_datetime(
                [
                    "2026-03-01 09:00:00Z",
                    "2026-03-01 09:20:00Z",
                    "2026-03-01 09:40:00Z",
                ],
                utc=True,
            ),
            "ExitedAt": pd.to_datetime(
                [
                    "2026-03-01 09:10:00Z",
                    "2026-03-01 09:30:00Z",
                    "2026-03-01 09:50:00Z",
                ],
                utc=True,
            ),
            "TradeDay": ["2026-03-01", "2026-03-01", "2026-03-01"],
            "PnL(Net)": [-300, -50, -20],
            "Size": [1, 5, 6],
        }
    )
    _, trades = compute.overtrading_detection(df, cap_loss_per_trade=200, cap_trades_after_big_loss=2)
    # Both trades after the big loss should be evaluated/tagged, not left as default LightBlue.
    assert trades.loc[trades["TradeIndex"] == 2, "TradeTag"].iloc[0] != "LightBlue"
    assert trades.loc[trades["TradeIndex"] == 3, "TradeTag"].iloc[0] != "LightBlue"
