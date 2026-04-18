from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditArtifact
from app.services.storage.base import ArtifactStore


class AuditCleanupService:
    """Deletes expired audit artifacts and marks their rows as deleted."""

    def __init__(self, artifact_store: ArtifactStore):
        self.artifact_store = artifact_store

    def cleanup_expired_artifacts(self, session: Session) -> int:
        now = datetime.now(UTC).replace(tzinfo=None)
        artifacts = list(
            session.scalars(
                select(AuditArtifact).where(
                    AuditArtifact.deleted_at.is_(None),
                    AuditArtifact.expires_at.is_not(None),
                    AuditArtifact.expires_at < now,
                )
            ).all()
        )
        for artifact in artifacts:
            if artifact.storage_path:
                self.artifact_store.delete(artifact.storage_path)
            artifact.deleted_at = now
        session.flush()
        return len(artifacts)
