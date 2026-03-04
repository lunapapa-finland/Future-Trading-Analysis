import pandas as pd

from dashboard.services.data.load_data import load_performance


def test_load_performance_keeps_trade_day_in_local_calendar(tmp_path):
    csv_path = tmp_path / "perf.csv"
    df = pd.DataFrame(
        {
            "TradeDay": ["2025-11-01", "2025-11-02"],
            "ContractName": ["MESZ5", "MESZ5"],
            "EnteredAt": ["2025-11-01T14:00:00Z", "2025-11-02T14:00:00Z"],
            "ExitedAt": ["2025-11-01T14:05:00Z", "2025-11-02T14:05:00Z"],
            "PnL(Net)": [1.0, 2.0],
        }
    )
    df.to_csv(csv_path, index=False)

    out = load_performance("MES", "2025-11-01", "2025-11-01", str(csv_path))
    assert len(out) == 1
    assert out["TradeDay"].dt.strftime("%Y-%m-%d").iloc[0] == "2025-11-01"
