# AGENT.md

Operator quick guide for data ingestion and analysis consistency.

## Source Of Truth
- Full operational details live in [README.md](./README.md), section:
  `Performance Import Workflow (Auto + Manual Steps)`.

## Daily Workflow (Short)
1. Drop new IBKR raw CSV files into `data/temp_performance/`.
2. Run importer (cron/job or manual): `jobs/run_perf_if_files.py`.
3. Importer updates:
   - `data/performance/Combined_performance_for_dash_project.csv`
   - `data/performance/trade_journal.csv` (key sync only)
4. Manually label journal rows in `trade_journal.csv`:
   - `Phase`, `Context`, `Setup`, `SignalBar`, `Comments`
5. Validate journal:
   - `GET /api/journal/validate` (optional symbol/start/end filters)
6. Use Analysis/Advanced Insights; metrics read journal fields when available.

## Manual vs Automatic
- Automatic:
  - Raw conversion, combined append/dedup, `trade_id`, journal key sync.
- Manual:
  - Trade annotation fields in `trade_journal.csv`.
  - Optional maintenance of `trade_journal_metadata.csv` allowed/preferred combos.

## Important Rule
- Do not manually edit `Combined_performance_for_dash_project.csv` unless recovering from corruption.
- Labels should be maintained in `trade_journal.csv` (and metadata rules file), not in combined performance.
