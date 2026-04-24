from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionDispatch
from app.services.workspace.targets import target_channel_key


class MessageDispatchBase:
    logger = logging.getLogger(__name__)

    def _current_debounce_seconds(self, session: Session) -> int:
        if not self.system_settings_service:
            return self.debounce_seconds
        current = self.system_settings_service.get_settings(session)
        return max(int(current.private_chat_debounce_seconds), 0)

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
