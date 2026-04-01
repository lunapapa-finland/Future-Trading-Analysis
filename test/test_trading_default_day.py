import pandas as pd

from dashboard.app import app
from dashboard.api import routes


def _seed_perf_csv(path):
    df = pd.DataFrame(
        {
            "TradeDay": ["2026-03-30", "2026-03-31"],
            "ContractName": ["MESM6", "MESM6"],
            "IntradayIndex": [1, 1],
            "EnteredAt": ["2026-03-30T14:30:00Z", "2026-03-31T14:30:00Z"],
            "ExitedAt": ["2026-03-30T14:40:00Z", "2026-03-31T14:40:00Z"],
            "PnL(Net)": [10.0, -5.0],
            "Type": ["Long", "Short"],
            "Size": [1, 1],
        }
    )
    df.to_csv(path, index=False)


def _seed_future_csv(path):
    df = pd.DataFrame(
        {
            "Datetime": [
                "2026-03-30 14:30:00+00:00",
                "2026-03-31 14:30:00+00:00",
            ],
            "Open": [5600.0, 5610.0],
            "High": [5605.0, 5615.0],
            "Low": [5595.0, 5605.0],
            "Close": [5602.0, 5612.0],
            "Volume": [1000, 1200],
        }
    )
    df.to_csv(path, index=False)


def test_trading_default_day_uses_performance_and_future_without_journal(tmp_path, monkeypatch):
    perf_csv = tmp_path / "perf.csv"
    future_csv = tmp_path / "future.csv"
    _seed_perf_csv(perf_csv)
    _seed_future_csv(future_csv)

    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setitem(routes.DATA_SOURCE_DROPDOWN, "MES", str(future_csv))
    monkeypatch.setattr(routes, "list_live_journal", lambda *args, **kwargs: [])

    client = app.test_client()
    resp = client.get("/api/trading/default-day?symbol=MES")
    assert resp.status_code == 200
    out = resp.get_json()
    assert out["day"] == "2026-03-31"
    assert out["source"] == "intersection(performance,future)"
