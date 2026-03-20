# Audit Layer Enhancement (Planned)

## Goal
Create a centralized audit layer so all mutating API actions are logged consistently to `data/audit/change_audit.jsonl` without relying on scattered manual instrumentation.

## Current State
- Audit logging exists and is active for key operations.
- Logging is event-based at selected call sites (`append_audit_event(...)`).
- It is not a strict middleware/decorator layer that guarantees coverage for every write path.

## Target Design
- Add a unified audit wrapper for mutating endpoints (`POST`, `PUT`, `PATCH`, `DELETE`).
- Standardize audit schema for every event:
  - `ts_utc`
  - `request_id`
  - `actor`
  - `endpoint`
  - `action`
  - `entity_type`
  - `entity_id`
  - `status` (`success` / `failure`)
  - `before_summary`
  - `after_summary`
  - `error`
- Keep service-level domain details in `details` while enforcing common envelope fields.

## Scope (Next Version)
- Trading Live writes:
  - journal create/edit/delete
  - day plan upsert
- Trading Match writes:
  - link, unlink, reconfirm
- Trade Upload writes:
  - parse preview decision outcome
  - commit merge
- Portfolio/config writes:
  - manual adjustments and config mutations

## Non-Goals
- Auditing all read-only `GET` endpoints.
- Storing full record snapshots for large datasets.
- Replacing business validation logic.

## Implementation Plan
1. Introduce `@audited_action(...)` decorator in backend API layer.
2. Enforce wrapper usage for all mutating routes.
3. Add request correlation id (`request_id`) generation and propagation.
4. Normalize actor extraction (session/basic auth/api job).
5. Add failure-path audit logging for rejected writes and exceptions.
6. Keep existing service events temporarily; then consolidate and remove duplicates.
7. Add tests to enforce coverage for every mutating route.

## Acceptance Criteria
- Every mutating endpoint writes one standardized audit event on success.
- Every mutating endpoint writes one standardized audit event on failure.
- Event fields are stable and queryable across modules.
- No silent write path exists without audit emission.

## Risks
- Duplicate events during migration.
- Overly large audit payloads if before/after summaries are not constrained.
- Performance impact if fsync is used too frequently per request.

## Mitigations
- Migration flag to disable legacy duplicate emitters route-by-route.
- Strict payload size cap for summaries/details.
- Optional buffered write mode for high-volume batch jobs.

## Suggested File Locations
- Decorator/wrapper: `src/dashboard/services/utils/audit_layer.py`
- Schema helpers: `src/dashboard/services/utils/audit_schema.py`
- Route integration: `src/dashboard/api/routes.py`
- Tests: `test/test_audit_layer.py`
