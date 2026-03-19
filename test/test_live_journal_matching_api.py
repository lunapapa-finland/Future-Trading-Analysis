import pandas as pd
from pathlib import Path
import io

from dashboard.app import app
from dashboard.api import routes
import dashboard.services.utils.journal_live as journal_live


def _seed_perf_csv(path):
    df = pd.DataFrame(
        {
            "trade_id": ["t1", "t2"],
            "TradeDay": ["2026-03-16", "2026-03-16"],
            "ContractName": ["MESH6", "MESH6"],
            "IntradayIndex": [1, 2],
            "EnteredAt": ["2026-03-16T14:30:00Z", "2026-03-16T15:20:00Z"],
            "ExitedAt": ["2026-03-16T14:40:00Z", "2026-03-16T15:45:00Z"],
            "EntryPrice": [5000.0, 5010.0],
            "ExitPrice": [5005.0, 5002.0],
            "PnL(Net)": [20.0, -35.0],
            "Type": ["Long", "Short"],
            "Size": [1, 2],
        }
    )
    df.to_csv(path, index=False)


def test_live_journal_upsert_and_list(tmp_path, monkeypatch):
    journal_csv = tmp_path / "journal_live.csv"
    adj_csv = tmp_path / "journal_adjustments.csv"
    match_csv = tmp_path / "journal_matches.csv"
    monkeypatch.setattr(journal_live, "JOURNAL_LIVE_CSV", str(journal_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_ADJUSTMENTS_CSV", str(adj_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_MATCHES_CSV", str(match_csv))

    client = app.test_client()
    resp = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 2,
                    "EntryPrice": 5000.0,
                    "ExitPrice": 5005.0,
                    "adjustments": [
                        {"AdjustmentType": "scale_in", "Qty": 1, "Price": 5001.0, "Note": "add"},
                    ],
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["inserted"] == 1

    listed = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16")
    assert listed.status_code == 200
    rows = listed.get_json()["rows"]
    assert len(rows) == 1
    assert rows[0]["TradeDay"] == "2026-03-16"
    assert rows[0]["Direction"] == "Long"
    assert len(rows[0]["adjustments"]) == 1


def test_live_journal_adjustments_append_and_update(tmp_path, monkeypatch):
    journal_csv = tmp_path / "journal_live.csv"
    adj_csv = tmp_path / "journal_adjustments.csv"
    match_csv = tmp_path / "journal_matches.csv"
    monkeypatch.setattr(journal_live, "JOURNAL_LIVE_CSV", str(journal_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_ADJUSTMENTS_CSV", str(adj_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_MATCHES_CSV", str(match_csv))

    client = app.test_client()
    create = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 1,
                    "adjustments": [
                        {"adjustment_id": "adj1", "AdjustmentType": "scale_in", "Qty": 1, "Price": 5001},
                    ],
                }
            ]
        },
    )
    assert create.status_code == 200
    row = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]
    jid = row["journal_id"]
    assert len(row["adjustments"]) == 1

    # Default mode append: keep existing + add new.
    append_resp = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "journal_id": jid,
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 1,
                    "adjustments": [
                        {"adjustment_id": "adj2", "AdjustmentType": "partial_exit", "Qty": 1, "Price": 5004},
                    ],
                }
            ]
        },
    )
    assert append_resp.status_code == 200
    row2 = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]
    ids = sorted([a["adjustment_id"] for a in row2["adjustments"]])
    assert ids == ["adj1", "adj2"]

    # Same id updates instead of duplicating.
    update_resp = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "journal_id": jid,
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 1,
                    "adjustments": [
                        {"adjustment_id": "adj2", "AdjustmentType": "partial_exit", "Qty": 2, "Price": 5006},
                    ],
                }
            ]
        },
    )
    assert update_resp.status_code == 200
    row3 = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]
    adj2 = [a for a in row3["adjustments"] if a["adjustment_id"] == "adj2"][0]
    assert adj2["Qty"] == "2.0"
    assert adj2["Price"] == "5006.0"


def test_matching_confirm_and_unlink(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    journal_csv = tmp_path / "journal_live.csv"
    adj_csv = tmp_path / "journal_adjustments.csv"
    match_csv = tmp_path / "journal_matches.csv"

    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_LIVE_CSV", str(journal_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_ADJUSTMENTS_CSV", str(adj_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_MATCHES_CSV", str(match_csv))

    client = app.test_client()
    create = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 1,
                    "EntryPrice": 5000.0,
                    "ExitPrice": 5005.0,
                }
            ]
        },
    )
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]

    ws = client.get("/api/journal/matching/workspace?trade_day=2026-03-16")
    assert ws.status_code == 200
    data = ws.get_json()
    assert len(data["performance_rows"]) == 2
    assert len(data["suggestions"]) >= 1

    confirm = client.post(
        "/api/journal/matching/confirm",
        json={
            "trade_day": "2026-03-16",
            "links": [{"journal_id": journal_id, "trade_id": "t1", "is_primary": True}],
            "replace_for_journal": True,
        },
    )
    assert confirm.status_code == 200
    c_body = confirm.get_json()
    assert c_body["ok"] is True
    assert c_body["inserted"] == 1

    ws2 = client.get("/api/journal/matching/workspace?trade_day=2026-03-16").get_json()
    assert len(ws2["active_matches"]) == 1

    unlink = client.post(
        "/api/journal/matching/unlink",
        json={"trade_day": "2026-03-16", "links": [{"journal_id": journal_id}]},
    )
    assert unlink.status_code == 200
    u_body = unlink.get_json()
    assert u_body["ok"] is True
    assert u_body["inactivated"] == 1


def test_critical_edit_marks_needs_reconfirm_and_inactivates_match(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    journal_csv = tmp_path / "journal_live.csv"
    adj_csv = tmp_path / "journal_adjustments.csv"
    match_csv = tmp_path / "journal_matches.csv"

    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_LIVE_CSV", str(journal_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_ADJUSTMENTS_CSV", str(adj_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_MATCHES_CSV", str(match_csv))

    client = app.test_client()
    create = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 1,
                    "EntryPrice": 5000.0,
                    "ExitPrice": 5005.0,
                }
            ]
        },
    )
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]

    confirm = client.post(
        "/api/journal/matching/confirm",
        json={
            "trade_day": "2026-03-16",
            "links": [{"journal_id": journal_id, "trade_id": "t1", "is_primary": True}],
            "replace_for_journal": True,
        },
    )
    assert confirm.status_code == 200
    ws_before = client.get("/api/journal/matching/workspace?trade_day=2026-03-16").get_json()
    assert len(ws_before["active_matches"]) == 1

    edit = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "journal_id": journal_id,
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 2,
                    "EntryPrice": 5000.0,
                    "ExitPrice": 5005.0,
                }
            ]
        },
    )
    assert edit.status_code == 200

    ws_after = client.get("/api/journal/matching/workspace?trade_day=2026-03-16").get_json()
    assert len(ws_after["active_matches"]) == 0
    row = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]
    assert row["MatchStatus"] == "needs_reconfirm"


def test_analysis_excludes_unmatched_by_default_when_matches_exist(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    journal_csv = tmp_path / "journal_live.csv"
    adj_csv = tmp_path / "journal_adjustments.csv"
    match_csv = tmp_path / "journal_matches.csv"

    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_LIVE_CSV", str(journal_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_ADJUSTMENTS_CSV", str(adj_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_MATCHES_CSV", str(match_csv))

    client = app.test_client()
    create = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 1,
                    "EntryPrice": 5000.0,
                    "ExitPrice": 5005.0,
                }
            ]
        },
    )
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]
    confirm = client.post(
        "/api/journal/matching/confirm",
        json={
            "trade_day": "2026-03-16",
            "links": [{"journal_id": journal_id, "trade_id": "t1", "is_primary": True}],
            "replace_for_journal": True,
        },
    )
    assert confirm.status_code == 200

    # Default include_unmatched=false => only matched trade_id rows are analyzed.
    core_default = client.post(
        "/api/analysis/pnl_distribution",
        json={"start_date": "2026-03-16", "end_date": "2026-03-16"},
    )
    assert core_default.status_code == 200
    assert len(core_default.get_json()) == 1

    core_with_unmatched = client.post(
        "/api/analysis/pnl_distribution",
        json={"start_date": "2026-03-16", "end_date": "2026-03-16", "include_unmatched": True},
    )
    assert core_with_unmatched.status_code == 200
    assert len(core_with_unmatched.get_json()) == 2


def test_analysis_excludes_all_when_no_active_matches_and_default_filter(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    journal_csv = tmp_path / "journal_live.csv"
    adj_csv = tmp_path / "journal_adjustments.csv"
    match_csv = tmp_path / "journal_matches.csv"

    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_LIVE_CSV", str(journal_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_ADJUSTMENTS_CSV", str(adj_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_MATCHES_CSV", str(match_csv))

    client = app.test_client()
    # No active matches created.
    core_default = client.post(
        "/api/analysis/pnl_distribution",
        json={"start_date": "2026-03-16", "end_date": "2026-03-16"},
    )
    assert core_default.status_code == 400
    body = core_default.get_json()
    assert body["code"] == "EMPTY_DATASET"


def test_matching_confirm_rejects_unknown_trade_id(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    journal_csv = tmp_path / "journal_live.csv"
    adj_csv = tmp_path / "journal_adjustments.csv"
    match_csv = tmp_path / "journal_matches.csv"

    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_LIVE_CSV", str(journal_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_ADJUSTMENTS_CSV", str(adj_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_MATCHES_CSV", str(match_csv))

    client = app.test_client()
    create = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 1,
                }
            ]
        },
    )
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]

    confirm = client.post(
        "/api/journal/matching/confirm",
        json={
            "trade_day": "2026-03-16",
            "links": [{"journal_id": journal_id, "trade_id": "not-real", "is_primary": True}],
            "replace_for_journal": True,
        },
    )
    assert confirm.status_code == 400
    assert "trade_id not found" in confirm.get_json()["error"]


def test_combined_performance_projects_matched_live_journal_labels(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    journal_csv = tmp_path / "journal_live.csv"
    adj_csv = tmp_path / "journal_adjustments.csv"
    match_csv = tmp_path / "journal_matches.csv"

    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_LIVE_CSV", str(journal_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_ADJUSTMENTS_CSV", str(adj_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_MATCHES_CSV", str(match_csv))

    client = app.test_client()
    create = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    "TradeDay": "2026-03-16",
                    "Phase": "Open",
                    "Context": "TR",
                    "Setup": "Wedge",
                    "SignalBar": "Doji",
                    "TradeIntent": "Runner",
                    "Direction": "Long",
                    "Size": 1,
                }
            ]
        },
    )
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]
    confirm = client.post(
        "/api/journal/matching/confirm",
        json={
            "trade_day": "2026-03-16",
            "links": [{"journal_id": journal_id, "trade_id": "t1", "is_primary": True}],
            "replace_for_journal": True,
        },
    )
    assert confirm.status_code == 200

    combined = client.get("/api/performance/combined?start=2026-03-16&end=2026-03-16")
    assert combined.status_code == 200
    rows = combined.get_json()
    t1 = [r for r in rows if r.get("trade_id") == "t1"][0]
    assert t1.get("Phase") == "Open"
    assert t1.get("Context") == "TR"
    assert t1.get("Setup") == "Wedge"
    assert t1.get("SignalBar") == "Doji"
    assert t1.get("TradeIntent") == "Runner"


def test_matching_parse_preview_endpoint_returns_preview_and_blocks_on_unbalanced_qty(tmp_path, monkeypatch):
    temp_perf = tmp_path / "temp_performance"
    temp_perf.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(routes, "TEMP_PERF_DIR", Path(temp_perf))

    client = app.test_client()
    data = {
        "files": (io.BytesIO(b"Date/Time,Symbol,Price,Quantity\n20260318;152815,MES,5000,1\n"), "upload.csv"),
    }
    resp = client.post("/api/journal/matching/parse-preview", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["can_continue"] is False
    assert body["hard_blocked"] is True
    assert len(body["saved_files"]) == 1
    assert len(body["unparseable_rows"]) >= 1


def test_matching_parse_preview_endpoint_archive_flag(tmp_path, monkeypatch):
    temp_perf = tmp_path / "temp_performance"
    temp_perf.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(routes, "TEMP_PERF_DIR", Path(temp_perf))

    client = app.test_client()
    data = {
        "files": (io.BytesIO(b"Date/Time,Symbol,Price,Quantity\n20260318;152815,MES,5000,1\n"), "upload.csv"),
        "archive_raw": "true",
    }
    resp = client.post("/api/journal/matching/parse-preview", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body.get("archived_files", [])) == 1
