import os
import secrets
import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, request, make_response
from dotenv import load_dotenv
from dashboard.api import register_api
from dashboard.config.env import LOGGING_PATH, LOG_DIR

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

load_dotenv("config/credentials.env")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)


# CORS / health handling
def _allow_health_and_preflight():
    if request.path == "/health":
        return None
    if request.method == "OPTIONS":
        resp = make_response("", 200)
        origin = os.environ.get("FRONTEND_ORIGIN", "*")
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        return resp
    return None


app.before_request(_allow_health_and_preflight)
app.add_url_rule("/health", "health", lambda: ("ok", 200))

# Register JSON API only
register_api(app)

server = app

__all__ = ["app", "server"]
