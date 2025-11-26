# Agent Reference – Future Trading Analysis

## What this project is
- Dash/Plotly dashboard (served via Flask/Gunicorn) that shows futures market candles and performance analytics for retail-sized contracts (MES, MNQ, M2K, M6E, M6B, MBT, MET).
- Two main tabs: Trading (charts, criteria) and Analysis (rolling win rate, drawdowns, Sharpe, etc.).
- Background jobs fetch daily market data and ingest dropped performance CSVs into combined datasets.

## Tech stack
- Python 3.x; Dash + dash-bootstrap-components + Plotly for UI; Flask/dash-auth for auth; pandas/numpy/scipy for data handling; yfinance for market pulls.
- Packaging via `setup.py`; Gunicorn entry in `wsgi.py` (`server` callable).
- Docker support with `docker-compose.yml` plus `docker/cron` jobs service.

## Key paths
- App entry: `src/dashboard/app.py`; WSGI: `wsgi.py` -> `dashboard.app`.
- Config/constants: `src/dashboard/config/settings.py`.
- Tabs: `src/dashboard/tabs/{trading_tab.py,analysis_tab.py}`.
- Callbacks: `src/dashboard/callbacks/{data_manager.py,display_manager.py}`.
- Data helpers: `src/dashboard/utils/data_acquisition.py` (yfinance daily 5m bars), `performance_acquisition.py` (process temp uploads).
- Background jobs: `jobs/run_trading_if_ready.py` (daily fetch after delay), `jobs/run_perf_if_files.py` (process temp CSVs).
- Data folders (created automatically): `data/future`, `data/performance`, `data/temp_performance`; logs in `log/`.
- Credentials (untracked): `src/dashboard/config/credentials.env` with `DASH_USER`, `DASH_PASS`, `SECRET_KEY`.

## How it runs (high level)
1) Data acquisition checks gaps up to last business day (holiday-aware via custom CME calendar) and appends validated 5m RTH bars to symbol CSVs under `data/future/`.
2) Performance ingestion watches `data/temp_performance/` for new CSVs, merges into `data/performance/Combined_performance_for_dash_project.csv`, and removes processed files.
3) Dash app loads data via callbacks, renders tabs, and protects everything with HTTP Basic auth; `/health` route bypasses auth for probes.

## Local dev quick notes
- Activate env (`finance_env.yml` for conda) or `pip install -r requirements.txt` then `pip install -e .`.
- Export creds: `set -a; . src/dashboard/config/credentials.env; set +a`.
- Run locally: `gunicorn -b 127.0.0.1:8050 --workers 2 --timeout 120 wsgi:server` or `make run`.
- Trigger jobs manually: `make data` (market fetch) / `make performance` (ingest temp performance).

## Docker
- `docker-compose.yml` builds web app and `trading_jobs` cron-like container; mount persistent volumes under `/srv/trading-dashboard/...` (see README).
- Health check: `curl http://127.0.0.1:8050/health` (no auth).

## Constraints/Gotchas for future edits
- Keep data/log directories path-safe for both local and Docker; settings resolve `PROJECT_ROOT`.
- Market data expects 81 RTH rows per day; acquisition interpolates minor gaps—avoid disrupting `validate_data` logic unless intentional.
- Auth/session key must be set via env; never commit credentials.
- Tests are minimal (`test_environment.py`); add targeted tests around data functions if changing logic.

## Fast orientation for an LLM agent
- Start from `src/dashboard/app.py` to see layout and callbacks registration.
- Use `src/dashboard/config/settings.py` for constants and file paths; touch cautiously.
- For new analytics, extend `analysis/compute.py` and `analysis/plots.py`, then surface via `analysis_tab.py`.
- For new data sources, adjust `DATA_SOURCE_DROPDOWN` and acquisition helpers; ensure CSV schema matches existing columns.
