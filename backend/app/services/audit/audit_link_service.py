from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLink, AuditRun


class AuditLinkService:
    """Records graph links between audit steps and artifacts."""

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
        link = AuditLink(
            run_id=run.id,
            source_artifact_id=source_artifact_id,
            source_step_id=source_step_id,
            target_artifact_id=target_artifact_id,
            target_step_id=target_step_id,
            relation=relation,
        )
        session.add(link)
        session.flush()
        return link
