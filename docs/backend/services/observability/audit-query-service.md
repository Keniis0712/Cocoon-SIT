# AuditQueryService

Source: `backend/app/services/observability/audit_query_service.py`

## Purpose

- Builds typed audit list/detail responses for observability APIs.
- Keeps route handlers free of direct audit graph assembly logic.

## Public Interface

- `list_runs(session) -> list[AuditRunOut]`
- `get_run_detail(session, run_id) -> AuditRunDetail`

## Interactions

- Used by `api/routes/observability/audits.py`.
- Reads `AuditRun`, `AuditStep`, `AuditArtifact`, and `AuditLink`.
