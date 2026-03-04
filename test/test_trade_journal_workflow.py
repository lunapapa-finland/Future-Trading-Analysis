import pandas as pd

from dashboard.services.utils import trade_journal as tj


def _perf_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "TradeDay": ["2025-11-01", "2025-11-01", "2025-11-02"],
            "ContractName": ["MES", "MES", "MES"],
            "IntradayIndex": [1, 2, 1],
            "PnL(Net)": [10, -5, 7],
        }
    )


def test_sync_trade_journal_is_idempotent(tmp_path):
    journal_path = tmp_path / "trade_journal.csv"
    perf = _perf_df()

    one = tj.sync_trade_journal(perf, path=str(journal_path))
    assert len(one) == 3

    two = tj.sync_trade_journal(perf, path=str(journal_path))
    assert len(two) == 3
    assert len(two.drop_duplicates(subset=tj.KEY_COLUMNS)) == 3

    # Preserve manual edits across sync runs.
    edited = two.copy()
    edited.loc[0, "Setup"] = "Wedge"
    edited.to_csv(journal_path, index=False)
    three = tj.sync_trade_journal(perf, path=str(journal_path))
    assert (three["Setup"] == "Wedge").any()


def test_validate_trade_journal_reports_missing_and_invalid():
    journal = pd.DataFrame(
        [
            {
                "TradeDay": "2025-11-01",
                "ContractName": "MES",
                "IntradayIndex": 1,
                "Phase": "",
                "Context": "TR",
                "Setup": "Wedge",
                "SignalBar": "Doji",
                "Comments": "",
            },
            {
                "TradeDay": "2025-11-01",
                "ContractName": "MES",
                "IntradayIndex": 2,
                "Phase": "Open",
                "Context": "BAD",
                "Setup": "Wedge",
                "SignalBar": "Doji",
                "Comments": "",
            },
        ]
    )
    meta = pd.DataFrame(
        [
            {"Phase": "Open", "Context": "*", "Setup": "*", "SignalBar": "*", "Validity": "allowed", "RuleNote": ""},
            {"Phase": "*", "Context": "TR", "Setup": "*", "SignalBar": "*", "Validity": "allowed", "RuleNote": ""},
            {"Phase": "*", "Context": "*", "Setup": "Wedge", "SignalBar": "*", "Validity": "allowed", "RuleNote": ""},
            {"Phase": "*", "Context": "*", "Setup": "*", "SignalBar": "Doji", "Validity": "allowed", "RuleNote": ""},
        ]
    )
    out = tj.validate_trade_journal(journal, metadata_df=meta)
    assert out["summary"]["RowsChecked"] == 2
    assert out["summary"]["Violations"] == 2
    issues = out["violations"]["Issue"].tolist()
    assert any("Phase:missing" in i for i in issues)
    assert any("Context:invalid_value(BAD)" in i for i in issues)


def test_merge_trade_journal_overrides_and_fills_fields():
    perf = pd.DataFrame(
        [
            {
                "TradeDay": "2025-11-01",
                "ContractName": "MES",
                "IntradayIndex": 1,
                "Setup": "LegacySetup",
                "Type": "Long",
            },
            {
                "TradeDay": "2025-11-01",
                "ContractName": "MES",
                "IntradayIndex": 2,
                "Setup": "LegacySetup2",
                "Type": "Short",
            },
        ]
    )
    journal = pd.DataFrame(
        [
            {
                "TradeDay": "2025-11-01",
                "ContractName": "MES",
                "IntradayIndex": 1,
                "Phase": "Open",
                "Context": "TR",
                "Setup": "ORB",
                "SignalBar": "StrongBull",
                "Comments": "ok",
            },
            {
                "TradeDay": "2025-11-01",
                "ContractName": "MES",
                "IntradayIndex": 2,
                "Phase": "",
                "Context": "",
                "Setup": "",
                "SignalBar": "",
                "Comments": "",
            },
        ]
    )
    merged = tj.merge_trade_journal(perf, journal_df=journal)
    row1 = merged.loc[merged["IntradayIndex"] == 1].iloc[0]
    row2 = merged.loc[merged["IntradayIndex"] == 2].iloc[0]

    assert row1["Setup"] == "ORB"
    assert row1["Phase"] == "Open"
    assert row1["Context"] == "TR"
    assert row1["SignalBar"] == "StrongBull"
    assert row2["Setup"] == "LegacySetup2"


def test_merge_trade_journal_prefers_trade_id_when_legacy_keys_change():
    perf = pd.DataFrame(
        [
            {
                "trade_id": "abc123",
                "TradeDay": "2025-11-02",
                "ContractName": "MES",
                "IntradayIndex": 99,
                "Setup": "LegacySetup",
                "Type": "Long",
            }
        ]
    )
    # Same trade_id but different legacy key fields should still merge.
    journal = pd.DataFrame(
        [
            {
                "trade_id": "abc123",
                "TradeDay": "2025-11-01",
                "ContractName": "MES",
                "IntradayIndex": 1,
                "Phase": "Open",
                "Context": "TR",
                "Setup": "ORB",
                "SignalBar": "StrongBull",
                "Comments": "id-linked",
            }
        ]
    )
    merged = tj.merge_trade_journal(perf, journal_df=journal)
    row = merged.iloc[0]
    assert row["Setup"] == "ORB"
    assert row["Phase"] == "Open"
    assert row["Comments"] == "id-linked"
