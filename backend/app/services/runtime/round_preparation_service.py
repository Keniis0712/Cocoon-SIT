from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ActionDispatch, AuditRun
from app.services.audit.service import AuditService
from app.services.runtime.round_cleanup import RoundCleanupService
from app.services.runtime.types import RuntimeEvent


class RoundPreparationService:
    """Prepares a runtime round before orchestration starts."""

    def __init__(
        self,
        audit_service: AuditService,
        round_cleanup: RoundCleanupService,
    ) -> None:
        self.audit_service = audit_service
        self.round_cleanup = round_cleanup

    def prepare(self, session: Session, action: ActionDispatch) -> tuple[RuntimeEvent, AuditRun]:
        if action.event_type == "edit":
            self.round_cleanup.cleanup_for_edit(
                session,
                cocoon_id=action.cocoon_id,
                chat_group_id=action.chat_group_id,
                edited_message_id=action.payload_json["message_id"],
            )
        elif action.event_type == "retry":
            self.round_cleanup.cleanup_for_retry(
                session,
                cocoon_id=action.cocoon_id,
                chat_group_id=action.chat_group_id,
                message_id=action.payload_json.get("message_id"),
            )
        event = RuntimeEvent(
            event_type=action.event_type,
            cocoon_id=action.cocoon_id,
            chat_group_id=action.chat_group_id,
            action_id=action.id,
            payload=action.payload_json,
        )
        audit_run = self.audit_service.start_run(
            session=session,
            cocoon_id=action.cocoon_id,
            chat_group_id=action.chat_group_id,
            action=action,
            operation_type=action.event_type,
        )
        return event, audit_run
