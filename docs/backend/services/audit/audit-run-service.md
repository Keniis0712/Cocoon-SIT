# AuditRunService

Source: `backend/app/services/audit/audit_run_service.py`

## Purpose

- Creates and finalizes `AuditRun` and `AuditStep` records.
- Centralizes lifecycle timestamps and status transitions for audit traces.

## Public Interface

- `start_run(session, cocoon_id, action, operation_type)`
- `finish_run(session, run, status)`
- `start_step(session, run, step_name, meta_json=None)`
- `finish_step(session, step, status)`

## Interactions

- Used by the `AuditService` facade.
- Called by runtime orchestration and durable-job flows through that facade.
