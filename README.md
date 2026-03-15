# Future Trading Analysis

Trading dashboard for futures market replay, performance analysis, portfolio tracking, and trade journaling.

## What It Does
- Serves a dashboard/API for candles, performance, analysis metrics, insights, portfolio, and trade tagging.
- Processes raw broker performance CSV exports from `data/temp_performance` into normalized trade records.
- Upserts trades into `data/performance/Performance_sum.csv` using stable trade identity (`trade_id` + signature dedupe).
- Auto-tags trade `Phase` during acquisition using CME session windows in central app config.
- Keeps analysis/trading timestamps aligned to CME time (`US/Central`).

## Project Layout
- `src/dashboard/` app, API routes, analytics, and merge/journal services
- `jobs/` scheduled job entrypoints
- `config/app_config.yaml` central runtime config (paths, UI defaults, analysis/session defaults)
- `data/` runtime data files (`future`, `metadata`, `performance`, `temp_performance`, `portfolio`)
- `web/` frontend app
- `test/` backend and API tests

## Screenshots
![Dashboard view](img/sample1.png)
![Trading view](img/sample2.png)
![Analysis view](img/sample3.png)
![Portfolio view](img/sample4.png)

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

Useful commands:
```bash
make docker-logs
make docker-job-trading
make docker-job-perf
```

## Raspberry Pi (Prebuilt Image)
Use the GHCR image override:
```bash
docker compose -f docker-compose.yml -f docker-compose.rpi.yml pull
docker compose -f docker-compose.yml -f docker-compose.rpi.yml up -d
```

Stop:
```bash
docker compose -f docker-compose.yml -f docker-compose.rpi.yml down
```

If GHCR is private, login first:
```bash
echo $GHCR_PAT | docker login ghcr.io -u <github-username> --password-stdin
```

## Data Merge Flow (Performance)
1. Put broker export CSV(s) in `data/temp_performance/`.
2. Run merge job (`make docker-job-perf` or `python jobs/run_perf_if_files.py`).
3. System converts files, deduplicates by trade signature, computes `trade_id`, auto-tags `Phase` (CME windows), upserts into performance file, and re-sorts by trade time.
4. Processed temp files are removed after successful merge.

Key files:
- `data/performance/Performance_sum.csv` (single source of truth for trade-level performance + tags)
- `data/metadata/tag_taxonomy.csv` (tag options + hints used across Guide/Trading/Analysis)
- `data/metadata/contract_specs.csv` (contract point/tick value mapping)
- `data/portfolio/cashflow.csv` and `data/portfolio/trade_sum.csv` (portfolio/equity inputs)

## Config Model
- Central config file: `config/app_config.yaml`
- Backend `/api/config` returns:
  - symbol catalog + source paths
  - UI options (timeframes/playback speeds)
  - analysis defaults
  - tag taxonomy
  - runtime manifest (active file paths + existence/readability/row counts)
- Config tab displays this manifest for operational verification.

## Timezone Policy
- Analysis/trading session APIs are evaluated on CME boundaries (`US/Central`).
- Candle and trade timestamps are normalized before filtering/sorting.
- Daily grouping (`TradeDay`) is CME-local.
- `Phase` auto-tagging uses configured CME windows:
  - Open: `08:30`-`10:00`
  - Middle: `10:00`-`14:00`
  - End: `14:00`-`15:10`

## Tests
```bash
pytest -q
```

## Notes
- Required secrets/env values are loaded from `src/dashboard/config/credentials.env`.
- Example env file: `src/dashboard/config/credentials.env.example`.
