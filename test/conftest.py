import pytest

from dashboard.app import app
import dashboard.services.portfolio as portfolio
import dashboard.services.analysis.portfolio_metrics as pm

# Ensure API auth checks are bypassed only in pytest context.
app.config["TESTING"] = True


@pytest.fixture
def client():
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def tmp_portfolio_csv(monkeypatch, tmp_path):
    cashflow_file = tmp_path / "cashflow.csv"
    trade_sum_file = tmp_path / "trade_sum.csv"
    cashflow_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(portfolio, "CASHFLOW_CSV", cashflow_file)
    monkeypatch.setattr(portfolio, "TRADE_SUM_CSV", trade_sum_file)
    monkeypatch.setattr(pm, "equity_series", portfolio.equity_series)
    yield
