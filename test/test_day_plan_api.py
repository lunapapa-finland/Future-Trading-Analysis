from dashboard.app import app
import dashboard.services.utils.day_plan as day_plan


def test_day_plan_upsert_and_list(tmp_path, monkeypatch):
    plan_csv = tmp_path / "day_plan.csv"
    monkeypatch.setattr(day_plan, "DAY_PLAN_CSV", str(plan_csv))

    client = app.test_client()
    resp = client.post(
        "/api/day-plan",
        json={
            "rows": [
                {
                    "Date": "2026-03-16",
                    "Bias": "Neutral",
                    "ExpectedDayType": "TR day",
                    "ActualDayType": "Trend day",
                    "KeyLevelsHTFContext": "HLOC around prior day high.",
                    "PrimaryPlan": "Trade failed breakouts near extremes.",
                    "AvoidancePlan": "Avoid chasing middle of range.",
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["inserted"] == 1

    listed = client.get("/api/day-plan?start=2026-03-16&end=2026-03-16")
    assert listed.status_code == 200
    rows = listed.get_json()["rows"]
    assert len(rows) == 1
    assert rows[0]["Date"] == "2026-03-16"
    assert rows[0]["ExpectedDayType"] == "TR day"
    assert rows[0]["ActualDayType"] == "Trend day"

    # Update same day should not 500 and should report update.
    resp2 = client.post(
        "/api/day-plan",
        json={
            "rows": [
                {
                    "Date": "2026-03-16",
                    "Bias": "Bullish",
                    "ExpectedDayType": "Trend day",
                }
            ]
        },
    )
    assert resp2.status_code == 200
    body2 = resp2.get_json()
    assert body2["updated"] == 1


def test_day_plan_rejects_weekend_date(tmp_path, monkeypatch):
    plan_csv = tmp_path / "day_plan.csv"
    monkeypatch.setattr(day_plan, "DAY_PLAN_CSV", str(plan_csv))
    client = app.test_client()
    # 2026-03-14 is Saturday
    resp = client.post(
        "/api/day-plan",
        json={"rows": [{"Date": "2026-03-14", "Bias": "Neutral"}]},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "weekday" in body["error"].lower()
