import json

from dashboard.app import app


def test_portfolio_get():
    client = app.test_client()
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "latest" in data
    assert "series" in data
    assert "risk_free_rate" in data
    assert "metrics" in data


def test_portfolio_adjust_validation():
    client = app.test_client()
    # bad reason
    resp = client.post("/api/portfolio/adjust", json={"reason": "foo", "amount": 10})
    assert resp.status_code == 400
    # bad amount
    resp = client.post("/api/portfolio/adjust", json={"reason": "deposit", "amount": -1})
    assert resp.status_code == 400
    # bad date
    resp = client.post("/api/portfolio/adjust", json={"reason": "deposit", "amount": 10, "date": "bad"})
    assert resp.status_code == 400
    # success
    resp = client.post("/api/portfolio/adjust", json={"reason": "deposit", "amount": 10, "date": "2025-01-01"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("ok") is True
