import pandas as pd

from dashboard.services.utils import performance_acquisition as pa
from dashboard.services.utils.trade_enrichment import ensure_trade_id
import dashboard.services.portfolio as portfolio


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
    monkeypatch.setattr(pa, "sync_trade_sum_from_performance_rows", lambda *args, **kwargs: None)
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
    monkeypatch.setattr(pa, "sync_trade_sum_from_performance_rows", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "merge_trade_labels", lambda df: df)

    out = pa.generate_aggregated_data([incoming])
    assert not out.empty


def test_generate_aggregated_data_preserves_distinct_trade_ids_with_same_signature(tmp_path, monkeypatch):
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
    monkeypatch.setattr(pa, "sync_trade_sum_from_performance_rows", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "merge_trade_labels", lambda df: df)

    out = pa.generate_aggregated_data([incoming])
    assert "trade_id" in out.columns
    assert out["trade_id"].nunique() == len(out)
    # Distinct trade_ids can legitimately share identical signature fields; do not collapse them.
    sig = ["ContractName", "EnteredAt", "ExitedAt", "EntryPrice", "ExitPrice", "Size", "Type"]
    assert out.duplicated(subset=sig).sum() >= 1


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
    monkeypatch.setattr(pa, "sync_trade_sum_from_performance_rows", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "merge_trade_labels", lambda df: df)
    out = pa.generate_aggregated_data([incoming])
    entered = pd.to_datetime(out["EnteredAt"], utc=True)
    assert entered.is_monotonic_increasing


def test_generate_aggregated_data_syncs_trade_sum_for_affected_days_only(tmp_path, monkeypatch):
    perf_csv = tmp_path / "combined.csv"
    trade_sum_csv = tmp_path / "trade_sum.csv"
    cashflow_csv = tmp_path / "cashflow.csv"

    base = pd.DataFrame(
        {
            "ContractName": ["MES", "MES"],
            "EnteredAt": ["2025-01-02T15:00:00Z", "2025-01-01T15:00:00Z"],
            "ExitedAt": ["2025-01-02T15:10:00Z", "2025-01-01T15:10:00Z"],
            "EntryPrice": [6000.0, 5999.0],
            "ExitPrice": [6001.0, 6000.0],
            "Size": [1, 1],
            "Type": ["Long", "Long"],
            "IntradayIndex": [1, 1],
            "Fees": [2.0, 2.0],
            "PnL(Net)": [8.0, 6.0],
        }
    )
    base = ensure_trade_id(base)
    base["YearMonth"] = ["2025-01", "2025-01"]
    base["TradeDay"] = ["2025-01-02", "2025-01-01"]
    base["DayOfWeek"] = ["Thursday", "Wednesday"]
    base["HourOfDay"] = [9, 9]
    base["TradeDuration"] = ["0 days 00:10:00", "0 days 00:10:00"]
    base["WinOrLoss"] = [1, 1]
    base["Streak"] = [1, 1]
    base["Comment"] = ["", ""]
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

    # Seed an existing trade_sum row for an unaffected day.
    trade_sum_seed = pd.DataFrame(
        [
            {"date": "2025-01-01", "trade_pnl": 6.0, "updated_at": "2026-01-01T00:00:00+00:00"},
            {"date": "2025-01-02", "trade_pnl": 8.0, "updated_at": "2026-01-01T00:00:00+00:00"},
        ]
    )
    trade_sum_seed.to_csv(trade_sum_csv, index=False)
    pd.DataFrame(columns=["event_id", "date", "amount", "reason", "created_at"]).to_csv(cashflow_csv, index=False)

    incoming = pd.DataFrame(
        {
            "Id": [1, 1],
            "ContractName": ["MES", "MES"],
            "EnteredAt": ["2025-01-02T15:00:00Z", "2025-01-03T15:00:00Z"],
            "ExitedAt": ["2025-01-02T15:10:00Z", "2025-01-03T15:10:00Z"],
            "EntryPrice": [6000.0, 6002.0],
            "ExitPrice": [6001.0, 6003.0],
            "Fees": [2.5, 2.0],
            "PnL": [7.5, 8.0],
            "Size": [1, 1],
            "Type": ["Long", "Long"],
            "TradeDay": ["2025-01-02", "2025-01-03"],
            "TradeDuration": ["0 days 00:10:00", "0 days 00:10:00"],
        }
    )

    monkeypatch.setattr(pa, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(pa, "merge_trade_labels", lambda df: df)
    monkeypatch.setattr(portfolio, "TRADE_SUM_CSV", trade_sum_csv)
    monkeypatch.setattr(portfolio, "CASHFLOW_CSV", cashflow_csv)

    pa.generate_aggregated_data([incoming])
    out = pd.read_csv(trade_sum_csv)
    by_day = {row["date"]: float(row["trade_pnl"]) for _, row in out.iterrows()}

    assert by_day["2025-01-01"] == 6.0  # unaffected day unchanged
    assert by_day["2025-01-02"] == 7.5  # corrected trade day updated
    assert by_day["2025-01-03"] == 8.0  # new trade day inserted


def test_apply_phase_tags_uses_cme_windows():
    # UTC timestamps corresponding to US/Central: 08:45, 11:15, 14:30 on the same day.
    df = pd.DataFrame(
        {
            "EnteredAt": [
                "2025-01-02T14:45:00Z",
                "2025-01-02T17:15:00Z",
                "2025-01-02T20:30:00Z",
            ]
        }
    )
    out = pa._apply_phase_tags(df)
    assert out["Phase"].tolist() == ["Open", "Middle", "End"]


def test_apply_phase_tags_handles_dst_before_and_after():
    # Before DST start in US/Central (CST, UTC-6): 2026-03-06 08:45 -> 14:45Z.
    # After DST start in US/Central (CDT, UTC-5): 2026-03-09 08:45 -> 13:45Z.
    df = pd.DataFrame(
        {
            "EnteredAt": [
                "2026-03-06T14:45:00Z",
                "2026-03-09T13:45:00Z",
            ]
        }
    )
    out = pa._apply_phase_tags(df)
    assert out["Phase"].tolist() == ["Open", "Open"]


def test_generate_aggregated_data_writes_audit_event(tmp_path, monkeypatch):
    perf_csv = tmp_path / "combined.csv"
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
    events = []
    monkeypatch.setattr(pa, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(pa, "sync_trade_sum_from_performance_rows", lambda *args, **kwargs: None)
    monkeypatch.setattr(pa, "merge_trade_labels", lambda df: df)
    monkeypatch.setattr(pa, "append_audit_event", lambda *args, **kwargs: events.append((args, kwargs)))

    out = pa.generate_aggregated_data([incoming])
    assert not out.empty
    assert len(events) == 1
    args, kwargs = events[0]
    assert args[0] == "performance_sum_merged"
    assert kwargs["actor"] == "job:acquire_missing_performance"
