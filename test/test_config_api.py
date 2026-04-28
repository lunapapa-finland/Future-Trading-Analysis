from dashboard.app import app
from dashboard.config.app_config import clear_app_config_cache
from dashboard.config.runtime_config import runtime_config_payload


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


def test_runtime_config_patch_updates_live_config(tmp_path, monkeypatch):
    cfg_path = tmp_path / "app_config.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "analysis:",
                "  risk_free_rate: 0.02",
                "  initial_net_liq: 10000",
                "ui:",
                "  playback_speeds: [15, 30]",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_PATH", str(cfg_path))
    clear_app_config_cache()

    client = app.test_client()
    resp = client.patch(
        "/api/runtime-config",
        json={
            "updates": {
                "analysis.risk_free_rate": 0.04,
                "ui.playback_speeds": "10, 20, 40",
                "tagging.strict_mode": False,
            }
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    values = {field["key"]: field["value"] for field in payload["fields"]}
    assert values["analysis.risk_free_rate"] == 0.04
    assert values["ui.playback_speeds"] == [10, 20, 40]
    assert values["tagging.strict_mode"] is False

    config_resp = client.get("/api/config")
    assert config_resp.status_code == 200
    config_payload = config_resp.get_json()
    assert config_payload["portfolio"]["risk_free_rate"] == 0.04
    assert config_payload["playback_speeds"] == [10, 20, 40]


def test_runtime_config_rejects_non_runtime_field(tmp_path, monkeypatch):
    cfg_path = tmp_path / "app_config.yaml"
    cfg_path.write_text("analysis:\n  risk_free_rate: 0.02\n", encoding="utf-8")
    monkeypatch.setenv("APP_CONFIG_PATH", str(cfg_path))
    clear_app_config_cache()

    client = app.test_client()
    resp = client.patch("/api/runtime-config", json={"updates": {"analysis.timezone": "Europe/Helsinki"}})
    assert resp.status_code == 400


def test_runtime_config_descriptions_come_from_yaml_comments(tmp_path, monkeypatch):
    cfg_path = tmp_path / "app_config.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "analysis:",
                "  # Annual test comment from YAML.",
                "  risk_free_rate: 0.02",
                "ui:",
                "  # Replay speeds test comment.",
                "  playback_speeds: [15, 30]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_PATH", str(cfg_path))
    clear_app_config_cache()

    payload = runtime_config_payload()
    descriptions = {field["key"]: field["description"] for field in payload["fields"]}
    assert descriptions["analysis.risk_free_rate"] == "Annual test comment from YAML."
    assert descriptions["ui.playback_speeds"] == "Replay speeds test comment."

    client = app.test_client()
    resp = client.patch("/api/runtime-config", json={"updates": {"analysis.risk_free_rate": 0.03}})
    assert resp.status_code == 200
    text = cfg_path.read_text(encoding="utf-8")
    assert "# Annual test comment from YAML." in text
    assert "risk_free_rate: 0.03" in text
