"""Rollback durable job execution service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Checkpoint, Cocoon, Message, SessionState
from app.models.entities import ActionStatus
from app.services.audit.service import AuditService
from app.services.runtime.round_cleanup import RoundCleanupService
from app.services.workspace.targets import get_session_state


class RollbackJobService:
    """Executes rollback jobs against checkpoints."""

    def __init__(
        self,
        audit_service: AuditService,
        round_cleanup: RoundCleanupService,
    ) -> None:
        self.audit_service = audit_service
        self.round_cleanup = round_cleanup

    def execute(self, session: Session, checkpoint_id: str) -> None:
        """Rollback a cocoon to a checkpoint anchor and record an audit summary."""
        checkpoint = session.get(Checkpoint, checkpoint_id)
        if not checkpoint:
            raise ValueError("Checkpoint not found")
        run = self.audit_service.start_run(session, checkpoint.cocoon_id, None, None, "rollback")
        step = self.audit_service.start_step(session, run, "rollback")
        anchor = session.get(Message, checkpoint.anchor_message_id)
        cocoon = session.get(Cocoon, checkpoint.cocoon_id)
        if not anchor or not cocoon:
            raise ValueError("Rollback anchor not found")
        later_messages = list(
            session.scalars(
                select(Message)
                .where(Message.cocoon_id == checkpoint.cocoon_id, Message.created_at > anchor.created_at)
                .order_by(Message.created_at.asc())
            ).all()
        )
        self.round_cleanup._delete_message_related_rows(session, [message.id for message in later_messages])
        cocoon.rollback_anchor_msg_id = checkpoint.anchor_message_id
        for item in session.scalars(
            select(Checkpoint).where(Checkpoint.cocoon_id == checkpoint.cocoon_id)
        ).all():
            item.is_active = item.id == checkpoint.id
        state = get_session_state(session, cocoon_id=checkpoint.cocoon_id)
        if state:
            state.active_tags_json = anchor.tags_json
            state.persona_json = state.persona_json | {"rollback_checkpoint_id": checkpoint.id}
        self.audit_service.record_json_artifact(
            session,
            run,
            step,
            "audit_summary",
            {
                "checkpoint_id": checkpoint.id,
                "deleted_message_ids": [message.id for message in later_messages],
                "anchor_message_id": checkpoint.anchor_message_id,
            },
            summary="Rollback execution summary",
        )
        self.audit_service.finish_step(session, step, ActionStatus.completed)
        self.audit_service.finish_run(session, run, ActionStatus.completed)
