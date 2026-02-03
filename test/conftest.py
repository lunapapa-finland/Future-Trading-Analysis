import pytest

from dashboard.app import app
import dashboard.services.portfolio as portfolio
import dashboard.services.analysis.portfolio_metrics as pm


@pytest.fixture
def client():
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def tmp_portfolio_csv(monkeypatch, tmp_path):
    tmp_file = tmp_path / "equity.csv"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(portfolio, "PORTFOLIO_CSV", tmp_file)
    monkeypatch.setattr(pm, "PORTFOLIO_CSV", tmp_file)
    monkeypatch.setattr(pm, "_read_rows", portfolio._read_rows)
    yield
