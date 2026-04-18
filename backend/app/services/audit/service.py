"""Audit service facade for runtime and durable job traces."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ActionDispatch, AuditArtifact, AuditLink, AuditRun, AuditStep
from app.services.audit.audit_artifact_service import AuditArtifactService
from app.services.audit.audit_cleanup_service import AuditCleanupService
from app.services.audit.audit_link_service import AuditLinkService
from app.services.audit.audit_run_service import AuditRunService
from app.services.storage.base import ArtifactStore


class AuditService:
    """Creates audit runs, steps, artifacts, and links for backend workflows."""

    def __init__(
        self,
        artifact_store: ArtifactStore,
        settings,
        run_service: AuditRunService | None = None,
        artifact_service: AuditArtifactService | None = None,
        link_service: AuditLinkService | None = None,
        cleanup_service: AuditCleanupService | None = None,
    ):
        self.artifact_store = artifact_store
        self.settings = settings
        self.run_service = run_service or AuditRunService()
        self.artifact_service = artifact_service or AuditArtifactService(artifact_store, settings)
        self.link_service = link_service or AuditLinkService()
        self.cleanup_service = cleanup_service or AuditCleanupService(artifact_store)

    def start_run(
        self,
        session: Session,
        cocoon_id: str | None,
        action: ActionDispatch | None,
        operation_type: str,
    ) -> AuditRun:
        return self.run_service.start_run(session, cocoon_id, action, operation_type)

    def finish_run(self, session: Session, run: AuditRun, status: str) -> AuditRun:
        return self.run_service.finish_run(session, run, status)

    def start_step(self, session: Session, run: AuditRun, step_name: str, meta_json: dict | None = None) -> AuditStep:
        return self.run_service.start_step(session, run, step_name, meta_json)

    def finish_step(self, session: Session, step: AuditStep, status: str) -> AuditStep:
        return self.run_service.finish_step(session, step, status)

    def record_json_artifact(
        self,
        session: Session,
        run: AuditRun,
        step: AuditStep | None,
        kind: str,
        payload: dict,
        summary: str | None = None,
        metadata_json: dict | None = None,
    ) -> AuditArtifact:
        return self.artifact_service.record_json_artifact(
            session,
            run,
            step,
            kind,
            payload,
            summary,
            metadata_json,
        )

    def record_link(
        self,
        session: Session,
        run: AuditRun,
        relation: str,
        *,
        source_artifact_id: str | None = None,
        source_step_id: str | None = None,
        target_artifact_id: str | None = None,
        target_step_id: str | None = None,
    ) -> AuditLink:
        return self.link_service.record_link(
            session,
            run,
            relation,
            source_artifact_id=source_artifact_id,
            source_step_id=source_step_id,
            target_artifact_id=target_artifact_id,
            target_step_id=target_step_id,
        )

    def cleanup_expired_artifacts(self, session: Session) -> int:
        return self.cleanup_service.cleanup_expired_artifacts(session)
