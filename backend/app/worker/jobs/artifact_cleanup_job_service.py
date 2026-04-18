"""Audit-artifact cleanup durable job execution service."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import AuditArtifact
from app.services.audit.service import AuditService


class ArtifactCleanupJobService:
    """Executes artifact cleanup requests."""

    def __init__(self, audit_service: AuditService) -> None:
        self.audit_service = audit_service

    def execute(
        self,
        session: Session,
        artifact_ids: list[str] | None = None,
        *,
        mode: str | None = None,
    ) -> None:
        """Delete explicit artifacts or fall back to TTL-based cleanup."""
        if (mode == "manual" or (mode is None and artifact_ids)) and artifact_ids:
            for artifact_id in artifact_ids:
                artifact = session.get(AuditArtifact, artifact_id)
                if artifact and artifact.deleted_at is None:
                    if artifact.storage_path:
                        self.audit_service.artifact_store.delete(artifact.storage_path)
                    artifact.deleted_at = datetime.now(UTC).replace(tzinfo=None)
            session.flush()
            return
        self.audit_service.cleanup_expired_artifacts(session)
