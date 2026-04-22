from __future__ import annotations

import logging

from sqlalchemy.orm import Session, sessionmaker

from app.models import ActionDispatch, FailedRound
from app.models.entities import ActionStatus
from app.services.jobs.chat_dispatch import ChatDispatchQueue
from app.services.runtime.chat_runtime import ChatRuntime


class ChatDispatchWorkerService:
    """Consumes chat dispatches and runs them through the runtime."""

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        chat_queue: ChatDispatchQueue,
        chat_runtime: ChatRuntime,
    ) -> None:
        self.session_factory = session_factory
        self.chat_queue = chat_queue
        self.chat_runtime = chat_runtime

    def process_next(self) -> bool:
        envelope = self.chat_queue.consume_next()
        if not envelope:
            return False
        self.logger.info(
            "Worker consumed chat dispatch envelope action_id=%s event_type=%s cocoon_id=%s chat_group_id=%s",
            envelope.action_id,
            getattr(envelope, "event_type", None),
            getattr(envelope, "cocoon_id", None),
            getattr(envelope, "chat_group_id", None),
        )
        with self.session_factory() as session:
            action = session.get(ActionDispatch, envelope.action_id)
            if not action:
                self.logger.warning(
                    "Worker could not find ActionDispatch action_id=%s; acknowledging envelope",
                    envelope.action_id,
                )
                self.chat_queue.ack(envelope)
                session.commit()
                return False
            action.status = ActionStatus.running
            action.started_at = action.started_at or action.queued_at
            session.flush()
            self.logger.info(
                "Worker starting runtime action_id=%s event_type=%s status=%s payload_keys=%s",
                action.id,
                action.event_type,
                action.status,
                sorted((action.payload_json or {}).keys()),
            )
            try:
                self.chat_runtime.run(session=session, action=action)
            except Exception as exc:  # noqa: BLE001
                self.logger.exception(
                    "Worker runtime failed action_id=%s event_type=%s cocoon_id=%s chat_group_id=%s",
                    envelope.action_id,
                    action.event_type if action else None,
                    action.cocoon_id if action else None,
                    action.chat_group_id if action else None,
                )
                session.rollback()
                action = session.get(ActionDispatch, envelope.action_id)
                if not action:
                    self.chat_queue.ack(envelope)
                    session.commit()
                    return True
                action.status = ActionStatus.failed
                action.error_text = str(exc)
                session.add(
                    FailedRound(
                        cocoon_id=action.cocoon_id,
                        chat_group_id=action.chat_group_id,
                        action_id=action.id,
                        event_type=action.event_type,
                        reason=str(exc),
                    )
                )
                session.commit()
                self.chat_queue.ack(envelope)
                return True
            self.logger.info(
                "Worker runtime completed action_id=%s event_type=%s",
                action.id,
                action.event_type,
            )
            session.commit()
        self.chat_queue.ack(envelope)
        return True
