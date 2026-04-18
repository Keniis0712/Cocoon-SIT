# AuditCleanupService

Source: `backend/app/services/audit/audit_cleanup_service.py`

## Purpose

- Deletes expired artifact files from storage.
- Marks matching `AuditArtifact` rows as soft-deleted.

## Public Interface

- `cleanup_expired_artifacts(session)`

## Interactions

- Used by the `AuditService` facade and artifact cleanup jobs.
- Depends on `ArtifactStore.delete(...)`.
