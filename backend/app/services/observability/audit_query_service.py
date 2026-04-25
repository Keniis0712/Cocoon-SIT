from __future__ import annotations

import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionDispatch, AuditArtifact, AuditLink, AuditRun, AuditStep, Message
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

    def _build_run_out(self, session: Session, run: AuditRun) -> AuditRunOut:
        user_message = session.scalar(
            select(Message)
            .where(
                Message.action_id == run.action_id,
                Message.role == "user",
            )
            .order_by(Message.created_at.asc())
            .limit(1)
        ) if run.action_id else None
        assistant_message = session.scalar(
            select(Message)
            .where(
                Message.action_id == run.action_id,
                Message.is_thought.is_(False),
                Message.role.in_(("assistant", "system")),
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        ) if run.action_id else None
        trigger_input = user_message.content if user_message else None
        if trigger_input is None and run.action_id:
            action = session.get(ActionDispatch, run.action_id)
            if action and isinstance(action.payload_json, dict):
                candidate = action.payload_json.get("content")
                if isinstance(candidate, str) and candidate.strip():
                    trigger_input = candidate
        return AuditRunOut(
            id=run.id,
            cocoon_id=run.cocoon_id,
            chat_group_id=run.chat_group_id,
            action_id=run.action_id,
            user_message_id=user_message.id if user_message else None,
            assistant_message_id=assistant_message.id if assistant_message else None,
            trigger_input=trigger_input,
            assistant_output=assistant_message.content if assistant_message else None,
            operation_type=run.operation_type,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )

    def list_runs(self, session: Session, user: User | None = None) -> list[AuditRunOut]:
        runs = list(session.scalars(select(AuditRun).order_by(AuditRun.started_at.desc())).all())
        if user is not None:
            runs = self.authorization_service.filter_visible_audit_runs(session, user, runs)
        return [self._build_run_out(session, run) for run in runs]

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
            run=self._build_run_out(session, run),
            steps=[AuditStepOut.model_validate(step) for step in steps],
            artifacts=[self._build_artifact_out(artifact) for artifact in artifacts],
            links=[AuditLinkOut.model_validate(link) for link in links],
        )
