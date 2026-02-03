from dashboard.app import app


def test_api_config_has_portfolio_and_timeframes():
    client = app.test_client()
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "symbols" in data
    assert isinstance(data.get("timeframes"), list)
    assert isinstance(data.get("playback_speeds"), list)
    portfolio = data.get("portfolio")
    assert portfolio is not None
    assert "initial_net_liq" in portfolio
    assert "start_date" in portfolio
    assert "risk_free_rate" in portfolio
