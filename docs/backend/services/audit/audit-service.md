# AuditService

Source: `backend/app/services/audit/service.py`

## Purpose

- Serves as the compatibility facade for the audit subsystem.
- Keeps existing callers on one interface while delegating to smaller audit services.

## Public Interface

- `start_run(session, cocoon_id, action, operation_type)`
- `finish_run(session, run, status)`
- `start_step(session, run, step_name, meta_json=None)`
- `finish_step(session, step, status)`
- `record_json_artifact(session, run, step, kind, payload, summary=None)`
- `record_link(session, run, relation, ...)`
- `cleanup_expired_artifacts(session)`

## Interactions

- Delegates run/step lifecycle to `AuditRunService`.
- Delegates artifact persistence to `AuditArtifactService`.
- Delegates graph edges to `AuditLinkService`.
- Delegates expiry cleanup to `AuditCleanupService`.
