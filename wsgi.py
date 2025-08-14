# wsgi.py
# If you run from the repo root, this imports the Dash app defined in app.py
# (which itself imports your "dashboard.*" package)
from dashboard.app import app as dash_app  
server = dash_app.server          # Gunicorn looks for "server"
