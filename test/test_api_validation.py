import pandas as pd

from dashboard.app import app
from dashboard.api import routes


def _seed_perf_csv(path):
    df = pd.DataFrame(
        {
            "TradeDay": ["2025-11-01"],
            "ContractName": ["MES"],
            "IntradayIndex": [1],
            "EnteredAt": ["2025-11-01T10:00:00Z"],
            "ExitedAt": ["2025-11-01T10:10:00Z"],
            "PnL(Net)": [10.0],
            "Type": ["Long"],
            "Size": [1],
        }
    )
    df.to_csv(path, index=False)


def test_analysis_rejects_invalid_granularity(tmp_path, monkeypatch):
    perf_csv = tmp_path / "perf.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))

    client = app.test_client()
    resp = client.post("/api/analysis/drawdown", json={"granularity": "1H"})
    assert resp.status_code == 400


def test_analysis_rejects_invalid_window_type(tmp_path, monkeypatch):
    perf_csv = tmp_path / "perf.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))

    client = app.test_client()
    resp = client.post("/api/analysis/rolling_win_rate", json={"window": "abc"})
    assert resp.status_code == 400


def test_analysis_rejects_invalid_start_date(tmp_path, monkeypatch):
    perf_csv = tmp_path / "perf.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))

    client = app.test_client()
    resp = client.post("/api/analysis/drawdown", json={"start_date": "not-a-date"})
    assert resp.status_code == 400


def test_insights_rejects_non_object_params(tmp_path, monkeypatch):
    perf_csv = tmp_path / "perf.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))

    client = app.test_client()
    resp = client.post("/api/insights", json={"params": []})
    assert resp.status_code == 400


def test_journal_tags_rejects_non_array_rows():
    client = app.test_client()
    resp = client.post("/api/journal/tags", json={"rows": {}})
    assert resp.status_code == 400


def test_analysis_date_filter_uses_trading_timezone_day_boundaries(tmp_path, monkeypatch):
    # 2025-11-01T02:10:00Z is still 2025-10-31 in US/Central.
    perf_csv = tmp_path / "perf.csv"
    df = pd.DataFrame(
        {
            "ContractName": ["MES", "MES"],
            "IntradayIndex": [1, 2],
            "EnteredAt": ["2025-11-01T02:00:00Z", "2025-11-01T15:00:00Z"],
            "ExitedAt": ["2025-11-01T02:10:00Z", "2025-11-01T15:10:00Z"],
            "PnL(Net)": [1.0, 2.0],
            "Type": ["Long", "Long"],
            "Size": [1, 1],
        }
    )
    df.to_csv(perf_csv, index=False)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))

    client = app.test_client()
    resp = client.post(
        "/api/analysis/drawdown",
        json={"start_date": "2025-11-01", "end_date": "2025-11-01", "include_unmatched": True},
    )
    assert resp.status_code == 200
    out = resp.get_json()
    assert isinstance(out, list)
    assert len(out) == 1


def test_analysis_date_filter_handles_dst_boundary_in_us_central(tmp_path, monkeypatch):
    # Around DST start (2026-03-08 in US/Central):
    # 05:30Z -> 2026-03-07 23:30 CST (previous day, should be excluded for 2026-03-08 filter)
    # 14:10Z -> 2026-03-08 09:10 CDT (same day, should be included)
    perf_csv = tmp_path / "perf.csv"
    df = pd.DataFrame(
        {
            "ContractName": ["MES", "MES"],
            "IntradayIndex": [1, 2],
            "EnteredAt": ["2026-03-08T05:20:00Z", "2026-03-08T14:00:00Z"],
            "ExitedAt": ["2026-03-08T05:30:00Z", "2026-03-08T14:10:00Z"],
            "PnL(Net)": [1.0, 2.0],
            "Type": ["Long", "Long"],
            "Size": [1, 1],
        }
    )
    df.to_csv(perf_csv, index=False)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))

    client = app.test_client()
    resp = client.post(
        "/api/analysis/drawdown",
        json={"start_date": "2026-03-08", "end_date": "2026-03-08", "include_unmatched": True},
    )
    assert resp.status_code == 200
    out = resp.get_json()
    assert isinstance(out, list)
    assert len(out) == 1
