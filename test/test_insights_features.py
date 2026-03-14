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

    compliance = compute.rule_compliance_score(
        df,
        max_trades_per_day=1,
        max_consecutive_losses=1,
        max_daily_loss=40,
        big_loss_threshold=40,
        max_trades_after_big_loss=0,
    )
    quality = compute.execution_quality_layer(df, min_trades=1)
    playbook = compute.playbook_builder(
        df,
        compliance_daily=compliance["daily"],
        execution_quality=quality,
        rules={
            "max_trades_per_day": 1,
            "max_consecutive_losses": 1,
            "max_daily_loss": 40,
            "big_loss_threshold": 40,
            "max_trades_after_big_loss": 0,
        },
        min_trades=2,
    )
    assert "highlights" in playbook
    assert "stop_doing" in playbook
    assert "action_items" in playbook
    assert len(playbook["action_items"]) >= 3
    assert {"Priority", "Why", "Action"}.issubset(set(playbook["action_items"][0].keys()))


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


def test_execution_quality_and_bundle():
    df = _fixture_df()
    quality = compute.execution_quality_layer(df, min_trades=1)
    assert "by_entry_hour" in quality and "by_hold_bucket" in quality
    assert len(quality["by_entry_hour"]) >= 1
    assert len(quality["by_hold_bucket"]) >= 1

    bundle = compute.insights_bundle(df, params={"min_trades": 2})
    assert "setup_journal" in bundle
    assert "rule_compliance" in bundle
    assert "execution_quality" in bundle
    assert "playbook" in bundle
    assert "monthly_report" in bundle
    assert "markdown" in bundle["monthly_report"]


def test_insights_bundle_month_scopes_all_sections():
    df = _fixture_df_with_months()
    bundle = compute.insights_bundle(df, params={"min_trades": 1, "month": "2025-01"})

    assert bundle["monthly_report"]["summary"]["Month"] == "2025-01"
    assert bundle["monthly_report"]["summary"]["Trades"] == 6

    total_trades_setup = sum(int(r.get("Trades", 0)) for r in bundle["setup_journal"])
    assert total_trades_setup == 6

    by_entry = bundle["execution_quality"]["by_entry_hour"]
    assert sum(int(r.get("Trades", 0)) for r in by_entry) == 6

    assert int(bundle["rule_compliance"]["summary"]["DaysAnalyzed"]) == 3


def test_setup_journal_explodes_multi_setup_tags():
    df = _fixture_df().copy()
    df.loc[0, "Setup"] = "Wedge | BO + Follow-through"
    journal = compute.setup_journal(df, min_trades=1)
    names = set(journal["Setup"].tolist())
    assert "Wedge" in names
    assert "BO + Follow-through" in names
