import pandas as pd

from dashboard.services.utils import performance_acquisition as pa
from dashboard.services.utils.trade_enrichment import ensure_trade_id


def test_generate_aggregated_data_updates_existing_trade_on_corrections(tmp_path, monkeypatch):
    perf_csv = tmp_path / "combined.csv"

    base = pd.DataFrame(
        {
            "ContractName": ["MES"],
            "EnteredAt": ["2025-01-02T15:00:00Z"],
            "ExitedAt": ["2025-01-02T15:10:00Z"],
            "EntryPrice": [6000.0],
            "ExitPrice": [6001.0],
            "Size": [1],
            "Type": ["Long"],
            "IntradayIndex": [1],
            "Fees": [2.0],
            "PnL(Net)": [8.0],
        }
    )
    base = ensure_trade_id(base)
    base["YearMonth"] = ["2025-01"]
    base["TradeDay"] = ["2025-01-02"]
    base["DayOfWeek"] = ["Thursday"]
    base["HourOfDay"] = [9]
    base["TradeDuration"] = ["0 days 00:10:00"]
    base["WinOrLoss"] = [1]
    base["Streak"] = [1]
    base["Comment"] = [""]
    base = base[
        [
            "trade_id",
            "YearMonth",
            "TradeDay",
            "DayOfWeek",
            "HourOfDay",
            "ContractName",
            "IntradayIndex",
            "EnteredAt",
            "ExitedAt",
            "EntryPrice",
            "ExitPrice",
            "Fees",
            "PnL(Net)",
            "Size",
            "Type",
            "TradeDuration",
            "WinOrLoss",
            "Streak",
            "Comment",
        ]
    ]
    base.to_csv(perf_csv, index=False)

    incoming = pd.DataFrame(
        {
            "Id": [1],
            "ContractName": ["MES"],
            "EnteredAt": ["2025-01-02T15:00:00Z"],
            "ExitedAt": ["2025-01-02T15:10:00Z"],
            "EntryPrice": [6000.0],
            "ExitPrice": [6001.0],
            "Fees": [2.5],
            "PnL": [7.5],
            "Size": [1],
            "Type": ["Long"],
            "TradeDay": ["2025-01-02"],
            "TradeDuration": ["0 days 00:10:00"],
        }
    )

    monkeypatch.setattr(pa, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(pa, "append_daily_equity", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "sync_trade_journal", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "merge_trade_labels", lambda df: df)

    final_df = pa.generate_aggregated_data([incoming])
    assert len(final_df) == 1
    assert float(final_df.iloc[0]["Fees"]) == 2.5
    assert float(final_df.iloc[0]["PnL(Net)"]) == 7.5


def test_generate_aggregated_data_handles_duplicate_trade_ids_without_crash(tmp_path, monkeypatch):
    perf_csv = tmp_path / "combined.csv"
    past = pd.DataFrame(
        {
            "trade_id": ["dup-1", "dup-1"],
            "YearMonth": ["2025-01", "2025-01"],
            "TradeDay": ["2025-01-02", "2025-01-02"],
            "DayOfWeek": ["Thursday", "Thursday"],
            "HourOfDay": [9, 9],
            "ContractName": ["MES", "MES"],
            "IntradayIndex": [1, 2],
            "EnteredAt": ["2025-01-02T15:00:00Z", "2025-01-02T15:01:00Z"],
            "ExitedAt": ["2025-01-02T15:10:00Z", "2025-01-02T15:11:00Z"],
            "EntryPrice": [6000.0, 6000.1],
            "ExitPrice": [6001.0, 6001.1],
            "Fees": [2.0, 2.0],
            "PnL(Net)": [8.0, 8.0],
            "Size": [1, 1],
            "Type": ["Long", "Long"],
            "TradeDuration": ["0 days 00:10:00", "0 days 00:10:00"],
            "WinOrLoss": [1, 1],
            "Streak": [1, 2],
            "Comment": ["", ""],
        }
    )
    past.to_csv(perf_csv, index=False)

    incoming = pd.DataFrame(
        {
            "Id": [1],
            "ContractName": ["MES"],
            "EnteredAt": ["2025-01-02T15:00:00Z"],
            "ExitedAt": ["2025-01-02T15:10:00Z"],
            "EntryPrice": [6000.0],
            "ExitPrice": [6001.0],
            "Fees": [2.5],
            "PnL": [7.5],
            "Size": [1],
            "Type": ["Long"],
            "TradeDay": ["2025-01-02"],
            "TradeDuration": ["0 days 00:10:00"],
        }
    )

    monkeypatch.setattr(pa, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(pa, "append_daily_equity", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "sync_trade_journal", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "merge_trade_labels", lambda df: df)

    out = pa.generate_aggregated_data([incoming])
    assert not out.empty


def test_generate_aggregated_data_removes_existing_signature_duplicates(tmp_path, monkeypatch):
    perf_csv = tmp_path / "combined.csv"
    dup_rows = pd.DataFrame(
        {
            "trade_id": ["a", "a-1"],
            "YearMonth": ["2025-01", "2025-01"],
            "TradeDay": ["2025-01-02", "2025-01-02"],
            "DayOfWeek": ["Thursday", "Thursday"],
            "HourOfDay": [9, 9],
            "ContractName": ["MES", "MES"],
            "IntradayIndex": [1, 2],
            "EnteredAt": ["2025-01-02T15:00:00Z", "2025-01-02T15:00:00Z"],
            "ExitedAt": ["2025-01-02T15:10:00Z", "2025-01-02T15:10:00Z"],
            "EntryPrice": [6000.0, 6000.0],
            "ExitPrice": [6001.0, 6001.0],
            "Fees": [2.0, 2.0],
            "PnL(Net)": [8.0, 8.0],
            "Size": [1, 1],
            "Type": ["Long", "Long"],
            "TradeDuration": ["0 days 00:10:00", "0 days 00:10:00"],
            "WinOrLoss": [1, 1],
            "Streak": [1, 2],
            "Comment": ["", ""],
        }
    )
    dup_rows.to_csv(perf_csv, index=False)
    incoming = pd.DataFrame(
        {
            "Id": [1],
            "ContractName": ["MES"],
            "EnteredAt": ["2025-01-02T15:00:00Z"],
            "ExitedAt": ["2025-01-02T15:10:00Z"],
            "EntryPrice": [6000.0],
            "ExitPrice": [6001.0],
            "Fees": [2.0],
            "PnL": [8.0],
            "Size": [1],
            "Type": ["Long"],
            "TradeDay": ["2025-01-02"],
            "TradeDuration": ["0 days 00:10:00"],
        }
    )
    monkeypatch.setattr(pa, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(pa, "append_daily_equity", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "sync_trade_journal", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "merge_trade_labels", lambda df: df)

    out = pa.generate_aggregated_data([incoming])
    sig = ["ContractName", "EnteredAt", "ExitedAt", "EntryPrice", "ExitPrice", "Size", "Type"]
    assert out.duplicated(subset=sig).sum() == 0


def test_generate_aggregated_data_sorts_chronologically(tmp_path, monkeypatch):
    perf_csv = tmp_path / "combined.csv"
    past = pd.DataFrame(
        {
            "trade_id": ["x2", "x1"],
            "YearMonth": ["2025-01", "2025-01"],
            "TradeDay": ["2025-01-02", "2025-01-01"],
            "DayOfWeek": ["Thursday", "Wednesday"],
            "HourOfDay": [10, 9],
            "ContractName": ["MES", "MES"],
            "IntradayIndex": [2, 1],
            "EnteredAt": ["2025-01-02T15:00:00Z", "2025-01-01T15:00:00Z"],
            "ExitedAt": ["2025-01-02T15:10:00Z", "2025-01-01T15:10:00Z"],
            "EntryPrice": [6001.0, 6000.0],
            "ExitPrice": [6002.0, 6001.0],
            "Fees": [2.0, 2.0],
            "PnL(Net)": [8.0, 8.0],
            "Size": [1, 1],
            "Type": ["Long", "Long"],
            "TradeDuration": ["0 days 00:10:00", "0 days 00:10:00"],
            "WinOrLoss": [1, 1],
            "Streak": [1, 1],
            "Comment": ["", ""],
        }
    )
    past.to_csv(perf_csv, index=False)
    incoming = pd.DataFrame(
        {
            "Id": [1],
            "ContractName": ["MES"],
            "EnteredAt": ["2025-01-03T15:00:00Z"],
            "ExitedAt": ["2025-01-03T15:10:00Z"],
            "EntryPrice": [6002.0],
            "ExitPrice": [6003.0],
            "Fees": [2.0],
            "PnL": [8.0],
            "Size": [1],
            "Type": ["Long"],
            "TradeDay": ["2025-01-03"],
            "TradeDuration": ["0 days 00:10:00"],
        }
    )
    monkeypatch.setattr(pa, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(pa, "append_daily_equity", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "sync_trade_journal", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "merge_trade_labels", lambda df: df)
    out = pa.generate_aggregated_data([incoming])
    entered = pd.to_datetime(out["EnteredAt"], utc=True)
    assert entered.is_monotonic_increasing
