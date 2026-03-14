from datetime import date

import dashboard.services.portfolio as portfolio
import dashboard.services.analysis.portfolio_metrics as pm
from dashboard.services.portfolio import append_manual, append_daily_equity, _init_if_missing
from dashboard.services.analysis.portfolio_metrics import portfolio_metrics, load_portfolio_df


def test_portfolio_metrics_uses_cashflows_and_trading(tmp_path, monkeypatch):
    cashflow_file = tmp_path / "cashflow.csv"
    trade_sum_file = tmp_path / "trade_sum.csv"
    cashflow_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(portfolio, "CASHFLOW_CSV", cashflow_file)
    monkeypatch.setattr(portfolio, "TRADE_SUM_CSV", trade_sum_file)
    monkeypatch.setattr(pm, "equity_series", portfolio.equity_series)
    _init_if_missing()
    append_manual(reason="deposit", amount=1000, date_override=str(date(2025, 1, 1)))
    append_daily_equity(date(2025, 1, 2), pnl=500)

    rows = portfolio.equity_series()
    latest_equity = float(rows[-1]["equity"])

    metrics = portfolio_metrics()
    assert metrics["latest_equity"] == latest_equity
    assert metrics["max_drawdown"] <= 0
    assert metrics["cagr"] is not None
    assert metrics["sharpe"] is not None


def test_backdated_manual_adjustment_recalculates_subsequent_equity(tmp_path, monkeypatch):
    cashflow_file = tmp_path / "cashflow.csv"
    trade_sum_file = tmp_path / "trade_sum.csv"
    cashflow_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(portfolio, "CASHFLOW_CSV", cashflow_file)
    monkeypatch.setattr(portfolio, "TRADE_SUM_CSV", trade_sum_file)
    monkeypatch.setattr(pm, "equity_series", portfolio.equity_series)

    _init_if_missing()
    append_daily_equity(date(2025, 1, 2), pnl=100)
    append_daily_equity(date(2025, 1, 3), pnl=200)
    append_manual(reason="deposit", amount=1000, date_override="2025-01-01")

    rows = portfolio.equity_series()
    by_date = {r["date"]: float(r["equity"]) for r in rows if r["reason"] == "trading" or r["reason"] == "deposit"}

    assert by_date["2025-01-01"] == 1000.0
    assert by_date["2025-01-02"] == 1100.0
    assert by_date["2025-01-03"] == 1300.0


def test_same_day_deposit_withdraw_are_separate_events(tmp_path, monkeypatch):
    cashflow_file = tmp_path / "cashflow.csv"
    trade_sum_file = tmp_path / "trade_sum.csv"
    cashflow_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(portfolio, "CASHFLOW_CSV", cashflow_file)
    monkeypatch.setattr(portfolio, "TRADE_SUM_CSV", trade_sum_file)

    _init_if_missing()
    append_manual(reason="deposit", amount=1000, date_override="2025-01-05")
    append_manual(reason="withdraw", amount=250, date_override="2025-01-05")
    events = [r for r in portfolio.equity_series() if r["date"] == "2025-01-05"]

    assert len(events) == 2
    assert events[0]["reason"] == "deposit"
    assert events[1]["reason"] == "withdraw"
    assert events[0].get("event_id")
    assert events[1].get("event_id")
    assert events[0]["event_id"] != events[1]["event_id"]
