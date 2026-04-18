# AuditArtifactService

Source: `backend/app/services/audit/audit_artifact_service.py`

## Purpose

- Persists JSON audit artifacts to storage.
- Records the corresponding `AuditArtifact` row, metadata, and expiry window.

## Public Interface

- `record_json_artifact(session, run, step, kind, payload, summary=None)`

## Interactions

- Used by the `AuditService` facade.
- Depends on `ArtifactStore` for the actual file write.
