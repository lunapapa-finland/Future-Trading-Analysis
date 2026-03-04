from datetime import date

import dashboard.services.portfolio as portfolio
import dashboard.services.analysis.portfolio_metrics as pm
from dashboard.services.portfolio import append_manual, append_daily_equity, _init_if_missing
from dashboard.config.analysis import INITIAL_NET_LIQ
from dashboard.services.analysis.portfolio_metrics import portfolio_metrics, load_portfolio_df


def test_portfolio_metrics_uses_cashflows_and_trading(tmp_path, monkeypatch):
    tmp_file = tmp_path / "equity.csv"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(portfolio, "PORTFOLIO_CSV", tmp_file)
    monkeypatch.setattr(pm, "_read_rows", portfolio._read_rows)
    monkeypatch.setattr(pm, "PORTFOLIO_CSV", tmp_file)
    _init_if_missing()
    append_manual(reason="deposit", amount=1000, date_override=str(date(2025, 1, 1)))
    append_daily_equity(date(2025, 1, 2), pnl=500)

    rows = portfolio._read_rows()
    latest_equity = float(rows[-1]["equity"])

    metrics = portfolio_metrics()
    assert metrics["latest_equity"] == latest_equity
    assert metrics["max_drawdown"] <= 0
    assert metrics["cagr"] is not None
    assert metrics["sharpe"] is not None


def test_backdated_manual_adjustment_recalculates_subsequent_equity(tmp_path, monkeypatch):
    tmp_file = tmp_path / "equity.csv"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(portfolio, "PORTFOLIO_CSV", tmp_file)
    monkeypatch.setattr(pm, "_read_rows", portfolio._read_rows)
    monkeypatch.setattr(pm, "PORTFOLIO_CSV", tmp_file)

    _init_if_missing()
    append_daily_equity(date(2025, 1, 2), pnl=100)
    append_daily_equity(date(2025, 1, 3), pnl=200)
    append_manual(reason="deposit", amount=1000, date_override="2025-01-01")

    rows = portfolio._read_rows()
    by_date = {r["date"]: float(r["equity"]) for r in rows}

    assert by_date["2025-01-01"] == INITIAL_NET_LIQ + 1000
    assert by_date["2025-01-02"] == INITIAL_NET_LIQ + 1100
    assert by_date["2025-01-03"] == INITIAL_NET_LIQ + 1300
