from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditArtifact
from app.schemas.observability.artifacts import ArtifactCleanupResult
from app.schemas.observability.audits import AuditArtifactOut
from app.services.storage.base import ArtifactStore


class ArtifactAdminService:
    """Handles typed artifact listing and cleanup workflows."""

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def list_artifacts(self, session: Session) -> list[AuditArtifactOut]:
        artifacts = list(session.scalars(select(AuditArtifact).order_by(AuditArtifact.created_at.desc())).all())
        return [AuditArtifactOut.model_validate(artifact) for artifact in artifacts]

    def cleanup_manual(self, session: Session, artifact_ids: list[str]) -> ArtifactCleanupResult:
        deleted = 0
        for artifact_id in artifact_ids:
            artifact = session.get(AuditArtifact, artifact_id)
            if not artifact or artifact.deleted_at is not None:
                continue
            if artifact.storage_path:
                self.artifact_store.delete(artifact.storage_path)
            artifact.deleted_at = datetime.now(UTC).replace(tzinfo=None)
            deleted += 1
        session.flush()
        return ArtifactCleanupResult(deleted=deleted)
