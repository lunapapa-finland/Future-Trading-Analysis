import os
import secrets
import logging
import json
import base64
import hmac
import hashlib
import time
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, request, make_response
from dotenv import load_dotenv
from dashboard.api import register_api
from dashboard.config.env import LOGGING_PATH, LOG_DIR
from dashboard.services.utils.data_init import ensure_required_csvs, validate_unified_taxonomy_or_raise

# Logging setup
os.makedirs(LOG_DIR, exist_ok=True)
file_handler = TimedRotatingFileHandler(
    filename=str(LOGGING_PATH), when="midnight", interval=1, backupCount=14, encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
file_handler.setLevel(logging.INFO)
root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(file_handler)

def _load_credentials_env() -> None:
    candidates = [
        "/app/src/dashboard/config/credentials.env",
        "src/dashboard/config/credentials.env",
        "config/credentials.env",
    ]
    for path in candidates:
        if os.path.exists(path):
            load_dotenv(path)
            return


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _session_secret() -> str:
    return os.environ.get("SESSION_SIGNING_KEY") or os.environ.get("SECRET_KEY", "")


def _verify_session_cookie(token: str) -> bool:
    if not token:
        return False
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        return False
    payload_b64 = parts[1]
    signature = parts[2]
    secret = _session_secret()
    if not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return False
    exp = int(payload.get("exp", 0))
    if exp <= 0:
        return False
    return int(exp) > int(time.time())


def _is_authorized() -> bool:
    auth = request.authorization
    if auth and auth.type and auth.type.lower() == "basic":
        expected_user = os.environ.get("DASH_USER", "")
        expected_pass = os.environ.get("DASH_PASS", "")
        if expected_user and expected_pass and auth.username == expected_user and auth.password == expected_pass:
            return True
    token = request.cookies.get("fta_session", "")
    return _verify_session_cookie(token)


_load_credentials_env()
ensure_required_csvs()
validate_unified_taxonomy_or_raise()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)


# CORS / health handling
def _allow_health_and_preflight():
    if request.path == "/health":
        return None
    allowed_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:8050")
    if allowed_origin == "*":
        allowed_origin = "http://localhost:8050"
    if request.method == "OPTIONS":
        resp = make_response("", 200)
        resp.headers["Access-Control-Allow-Origin"] = allowed_origin
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Vary"] = "Origin"
        return resp
    if app.testing:
        return None
    if request.path.startswith("/api/"):
        if _is_authorized():
            return None
        resp = make_response("unauthorized", 401)
        resp.headers["WWW-Authenticate"] = 'Basic realm="Future Trading API"'
        return resp
    return None


app.before_request(_allow_health_and_preflight)
app.add_url_rule("/health", "health", lambda: ("ok", 200))

# Register JSON API only
register_api(app)

server = app

__all__ = ["app", "server"]
