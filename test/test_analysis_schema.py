import pandas as pd
import pytest

from dashboard.services.analysis.schema import validate_performance_df


def test_validate_performance_df_success():
    df = pd.DataFrame(
        {
            "EnteredAt": ["2025-01-01T10:00:00Z"],
            "ExitedAt": ["2025-01-01T11:00:00Z"],
            "PnL(Net)": [100],
            "TradeDay": ["2025-01-01"],
        }
    )
    out = validate_performance_df(df)
    assert out["EnteredAt"].dtype == "datetime64[ns, UTC]"
    assert out["TradeDay"].iloc[0] == "2025-01-01"


def test_validate_performance_df_missing_cols():
    df = pd.DataFrame({"PnL(Net)": [1]})
    with pytest.raises(ValueError):
        validate_performance_df(df)


def test_validate_performance_df_bad_date():
    df = pd.DataFrame(
        {
            "EnteredAt": ["bad"],
            "ExitedAt": ["bad"],
            "PnL(Net)": [1],
        }
    )
    with pytest.raises(ValueError):
        validate_performance_df(df)
