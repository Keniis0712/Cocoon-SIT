from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import ActionDispatch, Message
from app.models.entities import ActionStatus
from app.services.workspace.targets import target_channel_key


class MessageDispatchBase:
    logger = logging.getLogger(__name__)

    def _current_debounce_seconds(self, session: Session, *, target_type: str = "cocoon") -> int:
        if not self.system_settings_service:
            return self.debounce_seconds
        current = self.system_settings_service.get_settings(session)
        if target_type == "chat_group":
            return max(int(current.group_chat_debounce_seconds), 0)
        return max(int(current.private_chat_debounce_seconds), 0)

    def _find_action_for_client_request_id(
        self,
        session: Session,
        client_request_id: str,
    ) -> ActionDispatch | None:
        existing = session.scalar(
            select(ActionDispatch).where(ActionDispatch.client_request_id == client_request_id)
        )
        if existing:
            return existing
        message_action_id = session.scalar(
            select(Message.action_id).where(Message.client_request_id == client_request_id)
        )
        if not message_action_id:
            return None
        return session.get(ActionDispatch, message_action_id)

    def _build_debounce_key(self, event_type: str, *parts: str | None) -> str:
        payload = "|".join((part or "").strip() for part in parts)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{event_type}:{digest}"

    def _find_debounced_action(
        self,
        session: Session,
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        event_type: str,
        debounce_key: str,
    ) -> ActionDispatch | None:
        now = datetime.now(UTC).replace(tzinfo=None)
        filters = [
            ActionDispatch.event_type == event_type,
            ActionDispatch.debounce_until.is_not(None),
            ActionDispatch.debounce_until > now,
        ]
        if cocoon_id:
            filters.extend(
                [ActionDispatch.cocoon_id == cocoon_id, ActionDispatch.chat_group_id.is_(None)]
            )
        if chat_group_id:
            filters.extend(
                [ActionDispatch.chat_group_id == chat_group_id, ActionDispatch.cocoon_id.is_(None)]
            )
        candidates = list(
            session.scalars(
                select(ActionDispatch)
                .where(*filters)
                .order_by(ActionDispatch.queued_at.desc())
                .limit(10)
            ).all()
        )
        return next(
            (item for item in candidates if item.payload_json.get("debounce_key") == debounce_key),
            None,
        )

    def _find_pending_chat_action(
        self,
        session: Session,
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
    ) -> ActionDispatch | None:
        filters = [
            ActionDispatch.event_type == "chat",
            ActionDispatch.status == ActionStatus.queued,
        ]
        if cocoon_id:
            filters.extend(
                [ActionDispatch.cocoon_id == cocoon_id, ActionDispatch.chat_group_id.is_(None)]
            )
        if chat_group_id:
            filters.extend(
                [ActionDispatch.chat_group_id == chat_group_id, ActionDispatch.cocoon_id.is_(None)]
            )
        return session.scalar(
            select(ActionDispatch)
            .where(*filters)
            .order_by(ActionDispatch.queued_at.desc())
            .limit(1)
        )

    def _claim_next_ready_action(self, session: Session) -> ActionDispatch | None:
        now = datetime.now(UTC).replace(tzinfo=None)
        candidates = list(
            session.scalars(
                select(ActionDispatch)
                .where(
                    ActionDispatch.status == ActionStatus.queued,
                    or_(
                        ActionDispatch.debounce_until.is_(None),
                        ActionDispatch.debounce_until <= now,
                    ),
                )
                .order_by(ActionDispatch.queued_at.asc())
                .limit(50)
            ).all()
        )
        for action in candidates:
            if self._has_prior_unfinished_chat_action(session, action):
                continue
            action.status = ActionStatus.running
            action.started_at = action.started_at or now
            session.flush()
            return action
        return None

    def _has_prior_unfinished_chat_action(
        self,
        session: Session,
        action: ActionDispatch,
    ) -> bool:
        if action.cocoon_id:
            target_filters = [
                ActionDispatch.cocoon_id == action.cocoon_id,
                ActionDispatch.chat_group_id.is_(None),
            ]
        elif action.chat_group_id:
            target_filters = [
                ActionDispatch.chat_group_id == action.chat_group_id,
                ActionDispatch.cocoon_id.is_(None),
            ]
        else:
            return False
        prior = session.scalar(
            select(ActionDispatch)
            .where(
                *target_filters,
                ActionDispatch.event_type == "chat",
                ActionDispatch.status.in_([ActionStatus.queued, ActionStatus.running]),
                ActionDispatch.id != action.id,
                or_(
                    ActionDispatch.queued_at < action.queued_at,
                    ActionDispatch.started_at.is_not(None),
                ),
            )
            .order_by(ActionDispatch.queued_at.asc())
            .limit(1)
        )
        return prior is not None

    def _commit_then_enqueue(
        self,
        session: Session,
        *,
        action: ActionDispatch,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        event_type: str,
        payload: dict,
    ) -> None:
        # Commit first so worker processes in other containers never see a queue
        # message before the corresponding ActionDispatch row exists.
        session.commit()
        queue_length = self.chat_queue.enqueue(
            action.id,
            event_type=event_type,
            cocoon_id=cocoon_id,
            chat_group_id=chat_group_id,
            payload=payload,
        )
        self.logger.info(
            "Enqueued chat dispatch action_id=%s event_type=%s cocoon_id=%s "
            "chat_group_id=%s queue_length=%s payload_keys=%s",
            action.id,
            event_type,
            cocoon_id,
            chat_group_id,
            queue_length,
            sorted(payload.keys()),
        )
        channel_key = target_channel_key(cocoon_id=cocoon_id, chat_group_id=chat_group_id)
        self.realtime_hub.publish(
            channel_key,
            {"type": "dispatch_queued", "action_id": action.id, "queue_length": queue_length},
        )
