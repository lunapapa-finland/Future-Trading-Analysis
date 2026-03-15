# SaaS Scaling and Migration Plan

## Purpose
This document consolidates two rollout tracks into a product roadmap for turning the current trading analysis app into a subscription SaaS for multiple users.

- Version 1: production-ready multi-tenant SaaS foundation (~1k users in year 1).
- Version 2 (2.0): scale and hardening path (~10k users, stronger SLO/compliance posture).

---

## Current-State Constraints
The current deployment is optimized for single-instance operation and local persistence.

- App and web runtime are coupled in one deployment unit.
- CSV files are used as mutable system-of-record.
- Background processing is cron-style, not queue-driven.
- Tenant/user isolation and subscription controls are not first-class.

These constraints are acceptable for local use but are not sufficient for subscription SaaS operations.

---

## Version 1: Production SaaS Foundation (Target: ~1k users)

### Goals
- Enable paid multi-user operation with workspace/tenant isolation.
- Replace CSV mutation with transactional persistence.
- Keep functionality parity for trading, tagging, portfolio, and insights.
- Add operational guardrails (auditability, retries, observability, backup).

### Target Architecture
- **Web**: Next.js service only.
- **API**: Flask/Gunicorn service only.
- **Worker**: async jobs service (Celery/RQ + Redis).
- **Data**:
  - Postgres = source of truth.
  - Redis = queue and hot-cache.
  - Object storage = export/audit snapshot artifacts.
- **Ingress**: load balancer / reverse proxy with TLS and request IDs.

### Data Model (minimum)
- Identity and tenancy: `users`, `workspaces`, `workspace_members`, `subscriptions`.
- Trading domain: `trades`, `trade_tags`, `daily_plans`, `cashflows`, `equity_points`.
- Configuration domain: `tag_taxonomy`, `rule_configs`, `app_configs`.
- Governance: `audit_events` (append-only), `idempotency_keys`.

### Product and Subscription Requirements
- Role model: `owner`, `editor`, `viewer` per workspace.
- Subscription model baseline:
  - Free: limited workspaces/trades/features.
  - Pro: full journaling/insights and exports.
  - Team: multi-seat collaboration and admin controls.
- Billing integration: Stripe (checkout, customer portal, webhooks).
- Entitlements middleware: API enforces feature access by plan.

### API and Contract Changes
- Versioned API under `/api/v1`.
- Standard response envelope:
  - `{ data, error, meta, request_id }`
- Tenant-scoped writes and reads by auth context (not client-provided tenant IDs).
- Idempotency required for mutating bulk endpoints.
- CSV endpoints become import/export only.

### Migration Strategy (V1)
1. **Foundation**
   - Add DB schema + migrations (Alembic).
   - Add auth + tenancy middleware.
   - Add audit event recording for all writes.
2. **Dual-write period**
   - Write to Postgres and CSV export mirror.
   - Keep current reads stable while parity is measured.
3. **Shadow read and parity checks**
   - Compare DB vs legacy outputs for key metrics.
   - Publish reconciliation reports (PnL, counts, tags, daily summaries).
4. **Cutover**
   - Switch read path to DB/materialized read models.
   - Stop CSV mutation.
   - Keep CSV as export artifact only.

### Operations and Reliability Baseline
- Structured logs with request/user/workspace correlation IDs.
- Metrics: latency, error rate, queue lag, job retries, DB connection saturation.
- Alerts on SLO breach and failed webhook processing.
- Daily backup + restore drill cadence.
- Security scanning in CI (Bandit, dependency audit, lint/type/test gates).

### V1 Acceptance Criteria
- No cross-tenant data access in integration tests.
- Idempotent bulk tag/day-plan writes are deterministic.
- DB output parity with legacy within tolerance.
- Core dashboard endpoints meet latency targets under expected concurrency.
- Subscription entitlements block gated features correctly.

---

## Version 2 (2.0): Scaling and Hardening (Target: ~10k users)

### Goals
- Improve throughput and reliability under sustained concurrent usage.
- Strengthen compliance/audit posture and incident recoverability.
- Reduce analytics latency variance with dedicated read models.

### 2.0 Architecture Enhancements
- Queue-first analytics and recomputation pipeline.
- Partitioning strategy for high-volume tables (tenant + time).
- Materialized read models for:
  - Portfolio/equity timelines
  - Tag/setup aggregates
  - Rule breach summaries
  - Day-plan vs outcome analytics
- Worker autoscaling by queue depth and SLA class.
- Tenant-aware rate limiting and noisy-neighbor controls.

### Data Integrity and Audit Hardening
- Append-only audit events as primary change history.
- Daily immutable snapshot export to object storage.
- Replay capability for historical reprocessing and incident recovery.
- Strong reconciliation tooling for drift detection across aggregate layers.

### Performance and SLO Targets (example)
- p95 core read API latency < 300ms at target load.
- Asynchronous analysis freshness < 60s for hot metrics, < 15m for deep reports.
- Queue lag alarm threshold with auto-scale trigger.
- Error budget policy by endpoint tier.

### 2.0 Migration Path
1. Enable DB-primary reads everywhere and retire legacy read paths.
2. Move heavy analytics to async workers with incremental recompute.
3. Introduce table partitioning and query tuning based on production telemetry.
4. Add feature flags for staged rollout by workspace cohorts.
5. Run disaster recovery and data replay drills before declaring 2.0 GA.

### 2.0 Exit Criteria
- Sustained load tests pass target SLOs.
- Migration/replay drills complete without data divergence.
- Audit exports and retention controls verified in production-like environment.
- Operational runbooks validated via incident simulation.

---

## Complexity and Feasibility Assessment

### High feasibility / lower complexity
- Service split (web/api/worker).
- API versioning + standardized contract.
- Tenant RBAC baseline.
- Billing integration for subscription gating.

### Medium complexity
- Dual-write migration and parity reconciliation.
- Idempotency and transaction safety on bulk writes.
- Materialized insights read models.

### Highest complexity and risk
- Deterministic historical import/replay.
- Queue correctness under retries and partial failures.
- Strict tenant isolation enforcement across all query paths.
- Operational maturity (SLOs, alert quality, runbook discipline).

### Feasibility conclusion
- The roadmap is feasible with phased delivery.
- Big-bang rewrite is high risk and not recommended.
- A staged migration with reconciliation and feature-flag cutovers is the safest path.

---

## Proposed Timeline (Indicative)
- V1 Foundation + dual-write + cutover: 6 to 10 weeks.
- 2.0 hardening and scale path: additional 6 to 10 weeks after stable V1 production telemetry.

Timeline depends on team capacity, migration data quality, and production validation windows.

---

## Immediate Next Steps
1. Approve canonical DB schema and tenancy model.
2. Define subscription tiers and entitlement matrix.
3. Implement API versioning and response envelope standard.
4. Start dual-write migration with reconciliation reporting.
5. Set initial SLOs and dashboards before production onboarding.
