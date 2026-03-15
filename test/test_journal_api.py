import pandas as pd

from dashboard.app import app
from dashboard.api import routes


def _seed_perf_csv(path):
    df = pd.DataFrame(
        {
            "trade_id": ["t1", "t2"],
            "TradeDay": ["2025-11-01", "2025-11-01"],
            "ContractName": ["MESZ25", "MESZ25"],
            "IntradayIndex": [1, 2],
            "EnteredAt": ["2025-11-01T10:00:00Z", "2025-11-01T11:00:00Z"],
            "ExitedAt": ["2025-11-01T10:10:00Z", "2025-11-01T11:10:00Z"],
            "PnL(Net)": [10.0, -5.0],
            "Type": ["Long", "Short"],
            "Size": [1, 1],
        }
    )
    df.to_csv(path, index=False)


def test_journal_tags_updates_performance_sum_csv(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))

    client = app.test_client()
    resp = client.post(
        "/api/journal/tags",
        json={
            "rows": [
                {
                    "trade_id": "t1",
                    "Phase": "Open",
                    "Context": "TR",
                    "SignalBar": "Doji",
                    "setups": ["Wedge", "DB/DT"],
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["updated"] == 1
    assert body["inserted"] == 0
    assert body["skipped"] == 0

    out = pd.read_csv(perf_csv)
    row = out.loc[out["trade_id"] == "t1"].iloc[0]
    assert row["Phase"] == "Open"
    assert row["Context"] == "TR"
    assert row["SignalBar"] == "Doji"
    assert row["Setup"] == "Wedge | DB/DT"


def test_journal_tags_skips_unknown_trade_keys(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))

    client = app.test_client()
    resp = client.post(
        "/api/journal/tags",
        json={
            "rows": [
                {
                    "trade_id": "not-found",
                    "Phase": "Open",
                    "Context": "TR",
                    "SignalBar": "Doji",
                    "setups": "Wedge",
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["updated"] == 0
    assert body["inserted"] == 0
    assert body["skipped"] == 1


def test_journal_tags_strict_mode_rejects_invalid_tag(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(routes, "get_app_config", lambda: {"tagging": {"strict_mode": True}})
    monkeypatch.setattr(
        routes,
        "taxonomy_payload",
        lambda: {
            "phase": [{"value": "Open"}],
            "context": [{"value": "TR"}],
            "setup": [{"value": "Wedge"}],
            "signal_bar": [{"value": "Doji"}],
        },
    )

    client = app.test_client()
    resp = client.post(
        "/api/journal/tags",
        json={"rows": [{"trade_id": "t1", "Phase": "InvalidPhase", "setups": "Wedge"}]},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "invalid Phase" in body["error"]
