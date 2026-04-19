from __future__ import annotations

import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditArtifact, AuditLink, AuditRun, AuditStep
from app.models import User
from app.schemas.observability.audits import (
    AuditArtifactOut,
    AuditLinkOut,
    AuditRunDetail,
    AuditRunOut,
    AuditStepOut,
)
from app.services.security.authorization_service import AuthorizationService
from app.services.storage.base import ArtifactStore


class AuditQueryService:
    """Builds typed audit query responses for observability APIs."""

    def __init__(self, authorization_service: AuthorizationService, artifact_store: ArtifactStore):
        self.authorization_service = authorization_service
        self.artifact_store = artifact_store

    def _load_artifact_payload(self, artifact: AuditArtifact):
        if artifact.deleted_at is not None or not artifact.storage_path:
            return None
        try:
            raw = self.artifact_store.read_text(artifact.storage_path)
        except FileNotFoundError:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def _build_artifact_out(self, artifact: AuditArtifact) -> AuditArtifactOut:
        return AuditArtifactOut(
            id=artifact.id,
            kind=artifact.kind,
            storage_backend=artifact.storage_backend,
            storage_path=artifact.storage_path,
            summary=artifact.summary,
            metadata_json=artifact.metadata_json,
            payload_json=self._load_artifact_payload(artifact),
            expires_at=artifact.expires_at,
            deleted_at=artifact.deleted_at,
            created_at=artifact.created_at,
        )

    def list_runs(self, session: Session, user: User | None = None) -> list[AuditRunOut]:
        runs = list(session.scalars(select(AuditRun).order_by(AuditRun.started_at.desc())).all())
        if user is not None:
            runs = self.authorization_service.filter_visible_audit_runs(session, user, runs)
        return [AuditRunOut.model_validate(run) for run in runs]

    def get_run_detail(self, session: Session, run_id: str, user: User | None = None) -> AuditRunDetail:
        run = session.get(AuditRun, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit run not found")
        if user is not None and not self.authorization_service.can_view_audit_run(session, user, run):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audit run access denied")
        steps = list(session.scalars(select(AuditStep).where(AuditStep.run_id == run.id)).all())
        artifacts = list(session.scalars(select(AuditArtifact).where(AuditArtifact.run_id == run.id)).all())
        links = list(session.scalars(select(AuditLink).where(AuditLink.run_id == run.id)).all())
        return AuditRunDetail(
            run=AuditRunOut.model_validate(run),
            steps=[AuditStepOut.model_validate(step) for step in steps],
            artifacts=[self._build_artifact_out(artifact) for artifact in artifacts],
            links=[AuditLinkOut.model_validate(link) for link in links],
        )
