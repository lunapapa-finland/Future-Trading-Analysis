import pandas as pd

from dashboard.services.analysis import compute


def _fixture_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "EnteredAt": pd.to_datetime(
                [
                    "2025-01-06 09:00:00Z",
                    "2025-01-06 10:00:00Z",
                    "2025-01-07 09:00:00Z",
                    "2025-01-07 10:00:00Z",
                    "2025-01-08 09:00:00Z",
                    "2025-01-08 10:00:00Z",
                ],
                utc=True,
            ),
            "ExitedAt": pd.to_datetime(
                [
                    "2025-01-06 09:20:00Z",
                    "2025-01-06 10:20:00Z",
                    "2025-01-07 09:25:00Z",
                    "2025-01-07 10:25:00Z",
                    "2025-01-08 09:30:00Z",
                    "2025-01-08 10:30:00Z",
                ],
                utc=True,
            ),
            "PnL(Net)": [100, -50, 60, -25, 110, -30],
            "Setup": ["ORBreak", "Fade", "ORBreak", "Fade", "ORBreak", "Fade"],
            "Type": ["Long", "Short", "Long", "Short", "Long", "Short"],
            "Size": [1, 1, 1, 1, 1, 1],
        }
    )


def _fixture_df_with_months() -> pd.DataFrame:
    base = _fixture_df()
    feb = base.copy()
    feb["EnteredAt"] = feb["EnteredAt"] - pd.Timedelta(days=31)
    feb["ExitedAt"] = feb["ExitedAt"] - pd.Timedelta(days=31)
    return pd.concat([feb, base], ignore_index=True)


def test_setup_journal_and_playbook():
    df = _fixture_df()
    journal = compute.setup_journal(df, min_trades=2)
    assert set(journal["Setup"].tolist()) == {"ORBreak", "Fade"}
    assert "Expectancy" in journal.columns

    playbook = compute.playbook_builder(df, min_trades=2)
    assert "highlights" in playbook
    assert "stop_doing" in playbook
    assert "action_items" in playbook
    assert len(playbook["action_items"]) >= 1


def test_rule_compliance_and_monthly_report():
    df = _fixture_df()
    compliance = compute.rule_compliance_score(df, max_trades_per_day=1, max_consecutive_losses=1, max_daily_loss=40)
    assert "summary" in compliance and "daily" in compliance
    assert len(compliance["daily"]) >= 1
    assert compliance["summary"]["DaysAnalyzed"] >= 1

    monthly = compute.monthly_review_report(df)
    assert monthly["summary"]["Trades"] == len(df)
    assert "focus_points" in monthly
    assert len(monthly["focus_points"]) == 3
    assert "markdown" in monthly


def test_mae_mfe_and_bundle():
    df = _fixture_df()
    mm = compute.mae_mfe_analytics(df, min_trades=2)
    assert "overall" in mm and "by_setup" in mm
    assert mm["overall"]["Trades"] == len(df)
    assert len(mm["by_setup"]) == 2

    bundle = compute.insights_bundle(df, params={"min_trades": 2})
    assert "setup_journal" in bundle
    assert "rule_compliance" in bundle
    assert "mae_mfe" in bundle
    assert "playbook" in bundle
    assert "monthly_report" in bundle
    assert "markdown" in bundle["monthly_report"]


def test_mae_mfe_prefers_real_columns_with_fallback():
    df = _fixture_df().copy()
    df["MFE"] = [120, 30, None, 40, 150, None]
    df["MAE"] = [20, 70, None, 15, 25, None]  # positive source values should normalize as adverse (negative)
    mm = compute.mae_mfe_analytics(df, min_trades=2)
    assert mm["overall"]["MFEColumn"] == "MFE"
    assert mm["overall"]["MAEColumn"] == "MAE"
    assert 0 < mm["overall"]["MFERealCoveragePct"] < 100
    assert 0 < mm["overall"]["MAERealCoveragePct"] < 100
    assert mm["overall"]["AvgMFE"] > 0
    assert mm["overall"]["AvgMAE"] <= 0


def test_insights_bundle_month_scopes_all_sections():
    df = _fixture_df_with_months()
    bundle = compute.insights_bundle(df, params={"min_trades": 1, "month": "2025-01"})

    assert bundle["monthly_report"]["summary"]["Month"] == "2025-01"
    assert bundle["monthly_report"]["summary"]["Trades"] == 6

    total_trades_setup = sum(int(r.get("Trades", 0)) for r in bundle["setup_journal"])
    assert total_trades_setup == 6

    assert int(bundle["mae_mfe"]["overall"]["Trades"]) == 6

    assert int(bundle["rule_compliance"]["summary"]["DaysAnalyzed"]) == 3
