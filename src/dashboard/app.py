"""
Compatibility shim for legacy imports.

The main Flask app lives in dashboard.core.app; this module re-exports it so
existing imports of `dashboard.app` continue to work.
"""

import os

from dashboard.core.app import app, server  # noqa: F401
from dashboard.config.env import PORT

__all__ = ["app", "server"]


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", str(PORT)))
    debug = os.environ.get("FLASK_DEBUG", "1").strip() in {"1", "true", "True"}
    app.run(host=host, port=port, debug=debug)
