# Future Trading Analysis

Futures trading workspace with replay, analysis, portfolio tracking, and taxonomy-driven trade/day journaling.

## What It Does
- Serves backend APIs and frontend UI for:
  - Trading session replay + per-trade tagging
  - Advanced analysis/insights
  - Portfolio equity tracking from `trade_sum` + manual cashflow events
  - Day-level pre/post market planning
- Processes broker exports from `data/temp_performance` into normalized trades.
- Upserts into `data/performance/Performance_sum.csv` using stable `trade_id` identity.
- Applies CME-time phase auto-tagging during merge (`Open`, `Middle`, `End`).
- Maintains append-only audit events for key data mutations.
- Includes day-plan plan-vs-outcome analytics in Advanced Insights and LLM Prompt Pack export.

## Current Source of Truth
- Trade performance + trade tags: `data/performance/Performance_sum.csv`
- Unified taxonomy (trade + day-plan): `data/metadata/taxonomy.csv`
- Day-level journal rows: `data/performance/day_plan.csv`
- Portfolio inputs: `data/portfolio/trade_sum.csv`, `data/portfolio/cashflow.csv`

## Project Layout
- `src/dashboard/` backend app, APIs, analytics, services
- `web/` Next.js frontend
- `jobs/` merge/acquisition job entrypoints
- `config/app_config.yaml` central runtime config
- `data/` runtime data folders
- `test/` backend/API tests

## Startup CSV Initialization
On backend startup, missing required CSV files are auto-created with headers (empty rows), without overwriting existing files.

Initializer:
- `src/dashboard/services/utils/data_init.py`

Hooked at app boot:
- `src/dashboard/core/app.py`

## Tagging + Day Plan Model
### Trade-level (Trading tab)
- `Phase`, `Context`, `Setup` (multi), `SignalBar`, `TradeIntent`
- Tag options come from unified taxonomy rows where `Domain=trade`

### Day-level (Trading tab)
- `Date`, `Bias`, `ExpectedDayType`, `ActualDayType`, `KeyLevelsHTFContext`, `PrimaryPlan`, `AvoidancePlan`
- Day-type/bias options come from unified taxonomy rows where `Domain=day_plan`
- Date selection is business-day constrained in UI (Mon-Fri options only) and enforced again in backend validation.

### Guide tab
- Reference workflow only (no persistent journal editing).

## Config Model
Central config file: `config/app_config.yaml`

Includes paths and defaults for:
- performance CSVs
- metadata CSVs
- portfolio CSVs
- analysis/session windows
- UI defaults

Runtime status is exposed through `/api/config` (`runtime_manifest`) and shown in Config tab.

## Advanced Insights (Day Plan Linked)
- Advanced Insights now contains a `day_plan_review` block (summary + daily table) computed from:
  - filtered trade performance (symbol/month/tag scope)
  - day journal rows (`day_plan.csv`)
- Current review metrics include:
  - planned vs unplanned trade-day counts
  - expected-vs-actual day-type match rate
  - bias alignment rate
  - planned vs unplanned PnL comparison
- LLM Prompt Pack export includes day-plan review summary/daily rows.

## Timezone Policy
- Analysis and session logic use CME timezone (`US/Central`).
- TradeDay grouping and phase tagging are CME-local.
- Default phase windows:
  - Open: `08:30`-`10:00`
  - Middle: `10:00`-`14:00`
  - End: `14:00`-`15:10`

## Quick Start (Conda)
```bash
conda activate finance_env
pip install -r requirements.txt
pip install -e .
```

Run locally:
```bash
make run-dev
```

Production-style local run:
```bash
make run
```

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

## Merge Flow (Performance)
1. Put broker export CSV files in `data/temp_performance/`.
2. Run merge job (`make docker-job-perf` or `python jobs/run_perf_if_files.py`).
3. Pipeline converts, normalizes, deduplicates, upserts, re-sorts, auto-tags phase, and updates impacted daily trade sums.
4. Processed temp files are removed after successful conversion.

## Tests
```bash
pytest -q
```

## Data Versioning Policy
- `data/metadata/**` is intended to be versioned (taxonomy/spec definitions).
- Runtime data (`data/performance`, `data/future`, `data/portfolio`, `data/temp_performance`) stays local/private by default.

## Auth / Env
- Credentials are loaded from `src/dashboard/config/credentials.env` when present.
- Example template: `src/dashboard/config/credentials.env.example`.
