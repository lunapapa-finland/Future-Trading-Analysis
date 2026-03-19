import pandas as pd

from dashboard.services.analysis import compute
from dashboard.services.utils.trade_enrichment import ensure_trade_id


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ContractName": ["MES", "MES"],
            "EnteredAt": pd.to_datetime(["2025-01-01 09:00:00Z", "2025-01-01 10:00:00Z"], utc=True),
            "ExitedAt": pd.to_datetime(["2025-01-01 09:20:00Z", "2025-01-01 10:20:00Z"], utc=True),
            "EntryPrice": [6000.0, 6005.0],
            "ExitPrice": [6002.0, 6001.0],
            "Size": [1, 1],
            "Type": ["Long", "Short"],
            "PnL(Net)": [10.0, -20.0],
        }
    )


def test_ensure_trade_id_is_present_and_deterministic():
    df = _df()
    one = ensure_trade_id(df)
    two = ensure_trade_id(df)
    assert "trade_id" in one.columns
    assert one["trade_id"].notna().all()
    assert one["trade_id"].tolist() == two["trade_id"].tolist()


def test_rule_compliance_uses_config_defaults(monkeypatch):
    monkeypatch.setattr(
        compute,
        "RULE_COMPLIANCE_DEFAULTS",
        {
            "max_trades_per_day": 1,
            "max_consecutive_losses": 1,
            "max_daily_loss": 9999.0,
            "big_loss_threshold": 9999.0,
            "max_trades_after_big_loss": 9,
        },
    )
    df = _df()
    out = compute.rule_compliance_score(df)
    assert out["summary"]["RuleBreaches"] >= 1
