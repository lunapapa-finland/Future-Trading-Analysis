import io
from pathlib import Path
from typing import Optional

import pandas as pd

from dashboard.app import app
from dashboard.api import routes
import dashboard.services.utils.journal_live as journal_live


def _seed_perf_csv(path):
    df = pd.DataFrame(
        {
            "trade_id": ["t1", "t2"],
            "TradeDay": ["2026-03-16", "2026-03-16"],
            "ContractName": ["MES", "MES"],
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


def _seed_contract_specs(path):
    pd.DataFrame(
        {
            "symbol": ["MES"],
            "point_value": [5.0],
            "tick_size": [0.25],
            "currency": ["USD"],
            "exchange": ["CME"],
        }
    ).to_csv(path, index=False)


def _patch_journal_storage(monkeypatch, tmp_path):
    journal_csv = tmp_path / "journal_live.csv"
    adj_csv = tmp_path / "journal_adjustments.csv"
    match_csv = tmp_path / "journal_matches.csv"
    specs_csv = tmp_path / "contract_specs.csv"
    _seed_contract_specs(specs_csv)
    monkeypatch.setattr(journal_live, "JOURNAL_LIVE_CSV", str(journal_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_ADJUSTMENTS_CSV", str(adj_csv))
    monkeypatch.setattr(journal_live, "JOURNAL_MATCHES_CSV", str(match_csv))
    monkeypatch.setattr(journal_live, "CONTRACT_SPECS_CSV", str(specs_csv))
    return journal_csv, adj_csv, match_csv


def _valid_adjustment(
    *,
    adjustment_id: str,
    qty: float = 1.0,
    entry: float = 5000.0,
    tp: float = 5004.0,
    sl: float = 4998.0,
    exit_price: Optional[float] = None,
):
    row = {
        "adjustment_id": adjustment_id,
        "LegIndex": 1,
        "Qty": qty,
        "EntryPrice": entry,
        "TakeProfitPrice": tp,
        "StopLossPrice": sl,
    }
    if exit_price is not None:
        row["ExitPrice"] = exit_price
    return row


def _valid_live_row(*, trade_intent: str = "Swing", adjustments=None, direction: str = "Long", setup: str = "Wedge"):
    if adjustments is None:
        adjustments = [_valid_adjustment(adjustment_id="adj1", exit_price=5005.0)]
    return {
        "TradeDay": "2026-03-16",
        "ContractName": "MES",
        "Phase": "Open",
        "Context": "TR",
        "Setup": setup,
        "SignalBar": "Doji",
        "TradeIntent": trade_intent,
        "Direction": direction,
        "Size": 1,
        "adjustments": adjustments,
    }


def _commit_payload_with_ids():
    # Required by /api/journal/matching/commit
    return [
        {
            "preview_trade_id": "t1",
            "trade_id": "t1",
            "ContractName": "MES",
            "EnteredAt": "2026-03-16T14:30:00Z",
            "ExitedAt": "2026-03-16T14:40:00Z",
            "EntryPrice": 5000.0,
            "ExitPrice": 5005.0,
            "Fees": 0.0,
            "PnL": 20.0,
            "Size": 1,
            "Type": "Long",
            "TradeDay": "2026-03-16",
            "TradeDuration": 10.0,
        },
        {
            "preview_trade_id": "t2",
            "trade_id": "t2",
            "ContractName": "MES",
            "EnteredAt": "2026-03-16T15:20:00Z",
            "ExitedAt": "2026-03-16T15:45:00Z",
            "EntryPrice": 5010.0,
            "ExitPrice": 5002.0,
            "Fees": 0.0,
            "PnL": -35.0,
            "Size": 2,
            "Type": "Short",
            "TradeDay": "2026-03-16",
            "TradeDuration": 25.0,
        },
    ]


def test_live_journal_upsert_and_list(tmp_path, monkeypatch):
    _patch_journal_storage(monkeypatch, tmp_path)
    client = app.test_client()

    resp = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
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
    _patch_journal_storage(monkeypatch, tmp_path)
    client = app.test_client()

    create = client.post(
        "/api/journal/live",
        json={
            "rows": [
                _valid_live_row(
                    trade_intent="Scale-in",
                    adjustments=[_valid_adjustment(adjustment_id="adj1", qty=1, entry=5001.0, tp=5004.0, sl=4998.0)],
                )
            ]
        },
    )
    assert create.status_code == 200
    row = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]
    jid = row["journal_id"]
    assert len(row["adjustments"]) == 1

    append_resp = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    **_valid_live_row(trade_intent="Scale-in", adjustments=[]),
                    "journal_id": jid,
                    "adjustments": [
                        _valid_adjustment(adjustment_id="adj2", qty=1, entry=5006.0, tp=5010.0, sl=5004.0),
                    ],
                }
            ]
        },
    )
    assert append_resp.status_code == 200
    row2 = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]
    ids = sorted([a["adjustment_id"] for a in row2["adjustments"]])
    assert ids == ["adj1", "adj2"]

    update_resp = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    **_valid_live_row(trade_intent="Scale-in", adjustments=[]),
                    "journal_id": jid,
                    "adjustments": [
                        _valid_adjustment(adjustment_id="adj2", qty=2, entry=5007.0, tp=5012.0, sl=5005.0),
                    ],
                }
            ]
        },
    )
    assert update_resp.status_code == 200
    row3 = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]
    adj2 = [a for a in row3["adjustments"] if a["adjustment_id"] == "adj2"][0]
    assert adj2["Qty"] == "2.0"
    assert adj2["EntryPrice"] == "5007.0"


def test_matching_confirm_and_unlink(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    _patch_journal_storage(monkeypatch, tmp_path)

    client = app.test_client()
    create = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]

    out = journal_live.confirm_matches(
        "2026-03-16",
        [{"journal_id": journal_id, "trade_id": "t1", "is_primary": True}],
        replace_for_journal=True,
    )
    assert out["inserted"] == 1

    links = client.get("/api/journal/matching/links?start=2026-03-16&end=2026-03-16")
    assert links.status_code == 200
    assert len(links.get_json()["rows"]) == 1

    unlink = client.post(
        "/api/journal/matching/unlink",
        json={"journal_id": journal_id, "trade_id": "t1", "trade_day": "2026-03-16"},
    )
    assert unlink.status_code == 200
    assert unlink.get_json()["inactivated"] == 1


def test_live_journal_delete_allowed_for_unmatched(tmp_path, monkeypatch):
    _patch_journal_storage(monkeypatch, tmp_path)
    client = app.test_client()

    create = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
    assert create.status_code == 200
    row = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]
    journal_id = row["journal_id"]

    deleted = client.delete("/api/journal/live", json={"journal_id": journal_id})
    assert deleted.status_code == 200
    body = deleted.get_json()
    assert body["deleted"] == 1
    assert body["deleted_adjustments"] == 1

    listed = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"]
    assert listed == []


def test_live_journal_delete_rejects_active_matched(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    _patch_journal_storage(monkeypatch, tmp_path)
    client = app.test_client()

    create = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]
    out = journal_live.confirm_matches(
        "2026-03-16",
        [{"journal_id": journal_id, "trade_id": "t1", "is_primary": True}],
        replace_for_journal=True,
    )
    assert out["inserted"] == 1

    deleted = client.delete("/api/journal/live", json={"journal_id": journal_id})
    assert deleted.status_code == 400
    assert "unlink first" in deleted.get_json()["error"]


def test_edit_rejects_when_journal_has_active_match(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    _patch_journal_storage(monkeypatch, tmp_path)

    client = app.test_client()
    create = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]

    out = journal_live.confirm_matches(
        "2026-03-16",
        [{"journal_id": journal_id, "trade_id": "t1", "is_primary": True}],
        replace_for_journal=True,
    )
    assert out["inserted"] == 1

    edit = client.post(
        "/api/journal/live",
        json={
            "rows": [
                {
                    **_valid_live_row(),
                    "journal_id": journal_id,
                    "adjustments": [_valid_adjustment(adjustment_id="adj1", qty=2, entry=5000.0, tp=5004.0, sl=4998.0, exit_price=5005.0)],
                }
            ]
        },
    )
    assert edit.status_code == 400
    assert "unlink first before editing" in edit.get_json()["error"]

    links_after = client.get("/api/journal/matching/links?start=2026-03-16&end=2026-03-16").get_json()["rows"]
    assert len(links_after) == 1


def test_analysis_excludes_unmatched_by_default_when_matches_exist(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    _patch_journal_storage(monkeypatch, tmp_path)

    client = app.test_client()
    create = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]
    journal_live.confirm_matches(
        "2026-03-16",
        [{"journal_id": journal_id, "trade_id": "t1", "is_primary": True}],
        replace_for_journal=True,
    )

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
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    _patch_journal_storage(monkeypatch, tmp_path)

    client = app.test_client()
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
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    _patch_journal_storage(monkeypatch, tmp_path)

    client = app.test_client()
    create = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]

    confirm = client.post(
        "/api/journal/matching/commit",
        json={
            "parsed_trades": _commit_payload_with_ids(),
            "links": [{"journal_id": journal_id, "preview_trade_id": "not-real", "is_primary": True}],
            "replace_for_journal": True,
        },
    )
    assert confirm.status_code == 400
    assert "preview trade id not found in parsed set" in confirm.get_json()["error"]


def test_combined_performance_projects_matched_live_journal_labels(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    _patch_journal_storage(monkeypatch, tmp_path)

    client = app.test_client()
    create = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]
    journal_live.confirm_matches(
        "2026-03-16",
        [{"journal_id": journal_id, "trade_id": "t1", "is_primary": True}],
        replace_for_journal=True,
    )

    combined = client.get("/api/performance/combined?start=2026-03-16&end=2026-03-16")
    assert combined.status_code == 200
    rows = combined.get_json()
    t1 = [r for r in rows if r.get("trade_id") == "t1"][0]
    assert t1.get("Phase") == "Open"
    assert t1.get("Context") == "TR"
    assert t1.get("Setup") == "Wedge"
    assert t1.get("SignalBar") == "Doji"
    assert t1.get("TradeIntent") == "Swing"


def test_trade_upload_parse_preview_endpoint_returns_preview_and_blocks_on_unbalanced_qty(tmp_path, monkeypatch):
    temp_perf = tmp_path / "temp_performance"
    temp_perf.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(routes, "TEMP_PERF_DIR", Path(temp_perf))

    client = app.test_client()
    data = {
        "files": (io.BytesIO(b"Date/Time,Symbol,Price,Quantity\n20260318;152815,MES,5000,1\n"), "upload.csv"),
    }
    resp = client.post("/api/trade-upload/parse-preview", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["can_continue"] is False
    assert body["hard_blocked"] is True
    assert len(body["saved_files"]) == 1
    assert len(body["unparseable_rows"]) >= 1


def test_trade_upload_parse_preview_endpoint_archive_flag(tmp_path, monkeypatch):
    temp_perf = tmp_path / "temp_performance"
    temp_perf.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(routes, "TEMP_PERF_DIR", Path(temp_perf))

    client = app.test_client()
    data = {
        "files": (io.BytesIO(b"Date/Time,Symbol,Price,Quantity\n20260318;152815,MES,5000,1\n"), "upload.csv"),
        "archive_raw": "true",
    }
    resp = client.post("/api/trade-upload/parse-preview", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body.get("archived_files", [])) == 1


def test_matching_relink_preview_loads_from_performance_sum(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    _patch_journal_storage(monkeypatch, tmp_path)
    client = app.test_client()

    create = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
    assert create.status_code == 200

    resp = client.get("/api/journal/matching/relink-preview?start=2026-03-16&end=2026-03-16")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert len(body["parsed_trades"]) == 2
    assert len(body["journal_rows"]) == 1
    assert body["can_continue"] is True


def test_trade_upload_commit_merges_performance(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    client = app.test_client()

    commit = client.post(
        "/api/trade-upload/commit",
        json={
            "parsed_trades": _commit_payload_with_ids(),
        },
    )
    assert commit.status_code == 200
    body = commit.get_json()
    assert body["ok"] is True
    assert body["merged"] is True


def test_matching_commit_link_only_skips_performance_merge(tmp_path, monkeypatch):
    perf_csv = tmp_path / "Performance_sum.csv"
    _seed_perf_csv(perf_csv)
    monkeypatch.setattr(routes, "PERFORMANCE_CSV", str(perf_csv))
    _patch_journal_storage(monkeypatch, tmp_path)
    client = app.test_client()

    create = client.post("/api/journal/live", json={"rows": [_valid_live_row()]})
    assert create.status_code == 200
    journal_id = client.get("/api/journal/live?start=2026-03-16&end=2026-03-16").get_json()["rows"][0]["journal_id"]

    commit = client.post(
        "/api/journal/matching/commit",
        json={
            "parsed_trades": _commit_payload_with_ids(),
            "links": [{"journal_id": journal_id, "preview_trade_id": "t1", "is_primary": True}],
            "replace_for_journal": True,
        },
    )
    assert commit.status_code == 200
    body = commit.get_json()
    assert body["ok"] is True
    assert body["merged"] is False
    assert body["rows_delta"] == 0
    assert body["matches_inserted"] == 1
