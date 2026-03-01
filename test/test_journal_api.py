import pandas as pd

from dashboard.app import app
from dashboard.api import routes
from dashboard.services.utils import trade_journal as tj


def test_journal_validate_api_reports_violations(tmp_path, monkeypatch):
    perf = pd.DataFrame(
        {
            "TradeDay": ["2025-11-01", "2025-11-01"],
            "ContractName": ["MES", "MES"],
            "IntradayIndex": [1, 2],
            "EnteredAt": ["2025-11-01T10:00:00Z", "2025-11-01T10:30:00Z"],
            "ExitedAt": ["2025-11-01T10:10:00Z", "2025-11-01T10:40:00Z"],
            "PnL(Net)": [10, -5],
            "Type": ["Long", "Short"],
            "Size": [1, 1],
        }
    )
    perf_csv = tmp_path / "perf.csv"
    perf.to_csv(perf_csv, index=False)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))

    journal = pd.DataFrame(
        {
            "TradeDay": ["2025-11-01", "2025-11-01"],
            "ContractName": ["MES", "MES"],
            "IntradayIndex": [1, 2],
            "Phase": ["", "Open"],
            "Context": ["TR", "BAD"],
            "Setup": ["Wedge", "Wedge"],
            "SignalBar": ["Doji", "Doji"],
            "Comments": ["", ""],
        }
    )
    meta = pd.DataFrame(
        [
            {"Phase": "Open", "Context": "*", "Setup": "*", "SignalBar": "*", "Validity": "allowed", "RuleNote": ""},
            {"Phase": "*", "Context": "TR", "Setup": "*", "SignalBar": "*", "Validity": "allowed", "RuleNote": ""},
            {"Phase": "*", "Context": "*", "Setup": "Wedge", "SignalBar": "*", "Validity": "allowed", "RuleNote": ""},
            {"Phase": "*", "Context": "*", "Setup": "*", "SignalBar": "Doji", "Validity": "allowed", "RuleNote": ""},
        ]
    )
    journal_csv = tmp_path / "trade_journal.csv"
    meta_csv = tmp_path / "trade_journal_metadata.csv"
    journal.to_csv(journal_csv, index=False)
    meta.to_csv(meta_csv, index=False)
    monkeypatch.setattr(tj, "TRADE_JOURNAL_CSV", str(journal_csv))
    monkeypatch.setattr(tj, "TRADE_JOURNAL_METADATA_CSV", str(meta_csv))

    client = app.test_client()
    resp = client.get("/api/journal/validate")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["summary"]["RowsChecked"] == 2
    assert body["summary"]["Violations"] == 2
