# ArtifactAdminService

Source: `backend/app/services/observability/artifact_admin_service.py`

## Purpose

- Provides typed artifact listing and manual cleanup workflows for admin APIs.

## Public Interface

- `list_artifacts(session) -> list[AuditArtifactOut]`
- `cleanup_manual(session, artifact_ids) -> ArtifactCleanupResult`

## Interactions

- Used by `api/routes/observability/admin_artifacts.py`.
- Depends on `ArtifactStore` to best-effort delete stored files.
