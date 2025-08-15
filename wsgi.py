import os, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent          # /app
SRC  = ROOT / "src"                                     # /app/src
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from dashboard.app import app as dash_app               # dash.Dash instance
server = dash_app.server                                # <-- WSGI callable
