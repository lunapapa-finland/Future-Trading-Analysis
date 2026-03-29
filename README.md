# Future Trading Analysis

Future Trading Analysis is a full-stack trading journal and replay workspace.
It combines:
- live journal capture,
- broker CSV upload and trade normalization,
- journal-to-trade matching,
- session replay with 5m candles,
- analysis and portfolio metrics,
- runtime visibility into data sources and fetch jobs.

## Functional Workflow (by UI tab)

### 1) Trading Guide (`/guide`)
- Displays operational rules and checklist flow.
- Reads taxonomy/day-plan taxonomy from backend so guidance matches your configured labels.

### 2) Trading Live (`/live`)
- Daily execution journal entry screen.
- Saves day-plan fields and per-trade journal rows.
- Enforces discipline constraints (max trades/day, max loss/day) from config.

### 3) Trade Upload (`/upload`)
- Upload broker CSV files.
- Parse preview detects malformed rows before commit.
- Reconciliation preview builds normalized trades and execution-leg pool.
- Commit writes into the combined performance dataset.

### 4) Trading Match (`/matching`)
- Loads relink workspace for a date range.
- Suggests journal-to-trade matches.
- Allows manual assign/unassign and commit with conflict checks.

### 5) Trading Details (`/trading`)
- Session replay view using raw 5m candles.
- Overlays trades and optional studies (EMA/VWAP/bar count).
- Exports markdown prompt pack for external LLM review.

### 6) Trading Analysis (`/analysis`)
- Core metrics (PnL growth, drawdown, rolling win rate, etc.).
- Advanced insights mode.
- Date filtering and bucketing are aligned to trading timezone boundaries.

### 7) Portfolio (`/portfolio`)
- Net liquidation history and metrics.
- Cashflow adjustments (deposit/withdraw).
- Trade-sum + cashflow integrated equity timeline.

### 8) Runtime Config (`/config`)
- Runtime manifest and file path visibility.
- Per-symbol data status.
- Manual data fetch trigger.
- Shows yfinance cooldown status and next available retry time.

## Architecture & Stack

### Backend
- Python + Flask API (`src/dashboard/core/app.py`)
- Pandas / NumPy for transformation and analytics
- CSV-based persistence (no DB required)

### Frontend
- Next.js (App Router) + TypeScript (`web/`)
- Tailwind CSS
- React Query for API data flows
- Charting: `klinecharts`, Chart.js (`react-chartjs-2`)

### Jobs
- `jobs/run_trading_if_ready.py`: market data fetch gate + acquisition run
- `jobs/run_perf_if_files.py`: merge temp performance files when present
- In Docker, cron invokes trading fetch gate every 10 minutes (`docker/cron/trading`)

## Timezone & Session Rules

Trading logic is anchored to CME local time (`US/Central`) from config:
- `analysis.timezone`
- `analysis.session.start = 08:30`
- `analysis.session.end = 15:10`

Important behavior:
- Session windows and analysis day boundaries follow trading timezone, not host machine timezone.
- DST transitions (US or Finland host timezone changes) do not shift the intended 08:30-15:10 Chicago session logic.

## Data Fetch, Cooldown, and "Next Try"

Manual fetch and scheduled job call the same backend acquisition path.

Rate-limit behavior:
- Shared cooldown is used to avoid repeated yfinance failures.
- Cooldown state is persisted in `YF_RATE_LIMIT_UNTIL_FILE` (default `/app/log/.yf_rate_limited_until` in container).
- While cooldown is active, fetch exits early (no symbol/day attempts).

Configurable defaults (`config/app_config.yaml`):
```yaml
data_fetch:
  rate_limit_cooldown_minutes: 60
  manual_max_retries: 3
  manual_retry_delay_seconds: 10
```

Precedence for cooldown minutes:
1. `YF_RATE_LIMIT_COOLDOWN_MINUTES` env var (if set)
2. `data_fetch.rate_limit_cooldown_minutes`
3. internal fallback

## Storage & Auto-Created Files

On startup, backend ensures required CSVs exist and seeds taxonomy when empty.

Core files:
- `data/performance/Performance_sum.csv`
- `data/performance/journal_live.csv`
- `data/performance/journal_adjustments.csv`
- `data/performance/journal_matches.csv`
- `data/performance/day_plan.csv`
- `data/portfolio/cashflow.csv`
- `data/portfolio/trade_sum.csv`
- `data/metadata/taxonomy.csv`
- `data/metadata/contract_specs.csv`
- `data/audit/change_audit.jsonl`

Per-symbol 5m future CSVs are under `data/future/` (for example `MES.csv`, `MNQ.csv`, ...).

## Configuration

### App config
Main runtime config file:
- `config/app_config.yaml`

Includes:
- path mapping,
- UI options,
- analysis/session timezone,
- discipline limits,
- data fetch defaults.

### Credentials / auth
Copy template and fill secrets:
- `src/dashboard/config/credentials.env.example` -> `src/dashboard/config/credentials.env`

Required values:
- `DASH_USER`
- `DASH_PASS`
- `SECRET_KEY`
- `SESSION_SIGNING_KEY`

## Local Development

### 1) Backend setup
```bash
conda activate finance_env
pip install -r requirements.txt
pip install -e .
```

### 2) Run backend API
```bash
make run-dev
```

Production-style local backend:
```bash
make run
```

### 3) Run frontend
```bash
cd web
npm ci
npm run dev
```

Default local ports:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8050` (dev) or as configured

## Docker

Build and start:
```bash
docker compose build --no-cache
docker compose up -d
```

Raspberry Pi deploy/upgrade:
```bash
docker compose -f docker-compose.yml -f docker-compose.rpi.yml pull
docker compose -f docker-compose.yml -f docker-compose.rpi.yml up -d
```

Useful commands:
```bash
make docker-logs
make docker-job-trading
make docker-job-perf
```

## Tests

Backend:
```bash
pytest -q
```

Frontend checks:
```bash
cd web
npm run typecheck
npm run lint
npm run test
```

## API Highlights

- `GET /api/config`
- `GET /api/data/fetch/status`
- `POST /api/data/fetch/run`
- `GET /api/trading/session`
- `POST /api/trading/llm-prompt`
- `POST /api/analysis/<metric>`
- `GET /api/portfolio`
- `POST /api/portfolio/adjust`

## Notes

- This project is CSV-first by design for transparent and portable storage.
- Runtime Config page is the fastest way to verify active paths, row counts, and fetch readiness.
