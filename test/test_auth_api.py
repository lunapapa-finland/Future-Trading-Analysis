import base64
import hashlib
import hmac
import json

import pytest

from dashboard.app import app


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _signed_session_token(secret: str) -> str:
    payload = {"v": 1, "sub": "test-user", "iat": 0, "n": "abc123"}
    payload_b64 = _b64url(json.dumps(payload).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"v1.{payload_b64}.{sig}"


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("DASH_USER", "test-user")
    monkeypatch.setenv("DASH_PASS", "test-pass")
    monkeypatch.setenv("SESSION_SIGNING_KEY", "test-session-secret")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    app.config["TESTING"] = False
    with app.test_client() as client:
        yield client
    app.config["TESTING"] = True


def test_api_requires_auth(auth_client):
    resp = auth_client.get("/api/config")
    assert resp.status_code == 401


def test_api_accepts_basic_auth(auth_client):
    token = base64.b64encode(b"test-user:test-pass").decode("utf-8")
    resp = auth_client.get("/api/config", headers={"Authorization": f"Basic {token}"})
    assert resp.status_code == 200


def test_api_accepts_valid_signed_session_cookie(auth_client):
    token = _signed_session_token(secret="test-session-secret")
    auth_client.set_cookie(key="fta_session", value=token, domain="localhost")
    resp = auth_client.get("/api/config")
    assert resp.status_code == 200


def test_api_rejects_invalid_signature_signed_session_cookie(auth_client):
    token = _signed_session_token(secret="wrong-secret")
    auth_client.set_cookie(key="fta_session", value=token, domain="localhost")
    resp = auth_client.get("/api/config")
    assert resp.status_code == 401
