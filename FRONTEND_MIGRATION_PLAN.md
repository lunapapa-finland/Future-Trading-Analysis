# Frontend Migration Plan (SoTA UI, Python backend intact)

## Scope & Constraints
- Frontend only: replace Dash UI with a modern web app; keep Python for data aggregation/analytics.
- Assume existing analytics in `src/dashboard/analysis/compute.py` stay stable; expose their outputs via JSON APIs (Flask/FastAPI layer) without changing logic.
- Preserve data folders (`data/future`, `data/performance`, `data/temp_performance`) and auth semantics (basic auth can be swapped for session/JWT at the API layer).

## Target Frontend Stack
- Framework: Next.js (React) + TypeScript.
- Styling: Tailwind CSS + design tokens; optional Radix/Headless UI for primitives.
- Data/State: TanStack Query for fetch/caching; SWR acceptable fallback.
- Charts: Visx/Recharts for perf; lightweight candlestick lib or Plotly wrapper only where needed.
- Timeframe handling: receive raw 5m bars and resample client-side for multi-timeframe (1m upsample optional; 15m/30m/1h/4h/D/W) similar to TradingView controls.
- Testing: Vitest + React Testing Library; Playwright for E2E; Storybook for components (optional but recommended).

## API Surface (thin Python layer)
Expose JSON endpoints that wrap current compute outputs:
- `GET /api/candles?symbol=...&start=...&end=...` -> CSV-backed futures bars (5m base). Client will resample for higher timeframes; optionally support `tf` param server-side if needed later.
- `GET /api/performance/combined` -> `Combined_performance_for_dash_project.csv`.
- `POST /api/analysis/<metric>` with payload `{ granularity?, window?, params... }` -> calls corresponding function in `analysis/compute.py` and returns JSON (arrays of records). Metrics: `pnl_growth`, `drawdown`, `pnl_distribution`, `behavioral_patterns`, `rolling_win_rate`, `sharpe_ratio`, `trade_efficiency`, `hourly_performance`, `performance_envelope`, `overtrading_detection`, `kelly_criterion`.
- Auth: basic auth passthrough initially; later swap to token/JWT if desired.

## Milestones
1) **API shim (Python)**
   - Add lightweight Flask/FastAPI blueprint under `api/` that loads data (same loaders as Dash) and exposes the endpoints above.
   - Return JSON with clear schemas; ensure datetime serialization to ISO strings.
   - Add CORS config for the new frontend origin.
   - Include transformation parity with existing Dash callbacks in `src/dashboard/callbacks/data_manager.py` and `display_manager.py` (these currently shape data for plots); mirror any pre-processing there or move to client when safe.

2) **Web scaffold**
   - Create `web/` Next.js app (TypeScript, Tailwind, ESLint/Prettier, React Query setup, env wiring).
   - Global layout shell (sidebar/nav, content area, toasts), route structure: `/trading`, `/analysis`, `/login` (if client-side gate needed).

3) **Feature parity – Trading**
   - Implement symbol selector, date range controls, fetch candles via `/api/candles`, render candlesticks + key stats.
   - Client-side timeframe selector (e.g., 5m/15m/30m/1h/4h/D/W) with resampling from 5m base; preserve OHLC correctness and gaps.
   - Add loading/error states, skeletons, and client-side caching of recent queries.

4) **Feature parity – Analysis**
   - Build query form mirroring existing Dash controls (granularity/window/metric).
   - For each metric, map response -> chart/table (line/area for rolling metrics, heatmap/table for behavioral patterns, envelope scatter+theory line, etc.).
   - Provide CSV export/download and basic bookmarking (query params in URL).

5) **UX polish & design system**
   - Finalize tokens (colors, spacing, typography), responsive grid, dark/light if desired.
   - Component library hardening (cards, tabs, tables, filters, chart wrappers).
   - Accessibility pass (focus states, keyboard nav).

6) **Validation & rollout**
   - Write component/unit tests for data mappers; E2E for core flows (login, trading view load, analysis query).
   - Compare outputs vs Dash for a sample dataset to verify parity.
   - Containerize `web/` (Next standalone) and update compose to run alongside Python services; enable healthcheck.

## Implementation Notes for Agents
- Keep compute contracts: do not mutate data shapes; if you add params, make them optional with defaults matching current behavior.
- When wrapping to JSON, ensure deterministic field order and ISO date strings (e.g., `2024-01-01T00:00:00Z`).
- Reuse existing loaders for CSV paths defined in `src/dashboard/config/settings.py` to avoid divergence.
- Review `src/dashboard/callbacks/` for any data shaping not in `analysis/compute.py`; replicate necessary transformations in the API layer or client mappers to keep chart inputs consistent.
- Candles: deliver raw 5m series; resample client-side with clear rules for OHLC aggregation and missing-bar handling; consider server-side optional downsample for heavy ranges.
- During migration, keep Dash running for side-by-side QA; new UI reads the same API.
- Avoid breaking logging/data directories; honor `PROJECT_ROOT`/env overrides in any new API layer.

## Open Decisions (to confirm when implementing)
- Auth mechanism for the new UI (continue basic auth via proxy/API vs. JWT).
- Hosting topology (same domain with path-based routing vs. subdomain for `web/`).
- Choice of candlestick library (Plotly wrapper vs. lightweight OSS) based on interactivity needs.
