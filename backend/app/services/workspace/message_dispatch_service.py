"""Workspace message/action dispatch orchestration service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionDispatch, Cocoon, Message, MessageTag, SessionState
from app.models.entities import ActionStatus
from app.services.jobs.chat_dispatch import ChatDispatchQueue
from app.services.realtime.hub import RealtimeHub


class MessageDispatchService:
    """Creates message-related action dispatches and publishes queue events."""

    DEFAULT_DEBOUNCE_SECONDS = 2

    def __init__(
        self,
        chat_queue: ChatDispatchQueue,
        realtime_hub: RealtimeHub,
        debounce_seconds: int | None = None,
    ) -> None:
        self.chat_queue = chat_queue
        self.realtime_hub = realtime_hub
        self.debounce_seconds = debounce_seconds or self.DEFAULT_DEBOUNCE_SECONDS

    def _build_debounce_key(self, event_type: str, *parts: str | None) -> str:
        payload = "|".join((part or "").strip() for part in parts)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{event_type}:{digest}"

    def _find_debounced_action(
        self,
        session: Session,
        cocoon_id: str,
        event_type: str,
        debounce_key: str,
    ) -> ActionDispatch | None:
        now = datetime.now(UTC).replace(tzinfo=None)
        candidates = list(
            session.scalars(
                select(ActionDispatch)
                .where(
                    ActionDispatch.cocoon_id == cocoon_id,
                    ActionDispatch.event_type == event_type,
                    ActionDispatch.debounce_until.is_not(None),
                    ActionDispatch.debounce_until > now,
                )
                .order_by(ActionDispatch.queued_at.desc())
                .limit(10)
            ).all()
        )
        return next(
            (
                item
                for item in candidates
                if item.payload_json.get("debounce_key") == debounce_key
            ),
            None,
        )

    def enqueue_chat_message(
        self,
        session: Session,
        cocoon_id: str,
        *,
        content: str,
        client_request_id: str,
        timezone: str,
    ) -> ActionDispatch:
        """Create a chat action and user message, enqueue it, and emit a queue event."""
        existing = session.scalar(
            select(ActionDispatch).where(ActionDispatch.client_request_id == client_request_id)
        )
        if existing:
            return existing
        debounce_key = self._build_debounce_key("chat", content)
        if existing_debounced := self._find_debounced_action(session, cocoon_id, "chat", debounce_key):
            return existing_debounced

        cocoon = session.get(Cocoon, cocoon_id)
        if not cocoon:
            raise ValueError("Cocoon not found")
        state = session.get(SessionState, cocoon_id)
        if not state:
            state = SessionState(cocoon_id=cocoon_id, persona_json={}, active_tags_json=[])
            session.add(state)
            session.flush()

        action = ActionDispatch(
            cocoon_id=cocoon_id,
            event_type="chat",
            status=ActionStatus.queued,
            client_request_id=client_request_id,
            debounce_until=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=self.debounce_seconds),
            payload_json={"timezone": timezone, "debounce_key": debounce_key},
        )
        session.add(action)
        session.flush()

        message = Message(
            cocoon_id=cocoon_id,
            action_id=action.id,
            client_request_id=client_request_id,
            role="user",
            content=content,
            tags_json=state.active_tags_json,
        )
        session.add(message)
        session.flush()
        action.payload_json = {
            "message_id": message.id,
            "client_request_id": client_request_id,
            "timezone": timezone,
            "debounce_key": debounce_key,
        }
        for tag in state.active_tags_json:
            session.add(MessageTag(message_id=message.id, tag_id=tag))
        session.flush()
        queue_length = self.chat_queue.enqueue(action.id, cocoon_id, "chat", action.payload_json)
        self.realtime_hub.publish(
            cocoon_id,
            {"type": "dispatch_queued", "action_id": action.id, "queue_length": queue_length},
        )
        return action

    def enqueue_user_message_edit(
        self,
        session: Session,
        cocoon_id: str,
        *,
        message: Message,
        content: str,
    ) -> ActionDispatch:
        """Update a user message and enqueue a follow-up edit action."""
        debounce_key = self._build_debounce_key("edit", message.id, content)
        if existing_debounced := self._find_debounced_action(session, cocoon_id, "edit", debounce_key):
            return existing_debounced
        message.content = content
        action = ActionDispatch(
            cocoon_id=cocoon_id,
            event_type="edit",
            status=ActionStatus.queued,
            debounce_until=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=self.debounce_seconds),
            payload_json={"message_id": message.id, "debounce_key": debounce_key},
        )
        session.add(action)
        session.flush()
        queue_length = self.chat_queue.enqueue(action.id, cocoon_id, "edit", action.payload_json)
        self.realtime_hub.publish(
            cocoon_id,
            {"type": "dispatch_queued", "action_id": action.id, "queue_length": queue_length},
        )
        return action

    def enqueue_retry(
        self,
        session: Session,
        cocoon_id: str,
        *,
        message_id: str | None,
    ) -> ActionDispatch:
        """Create and enqueue a retry action for a cocoon."""
        debounce_key = self._build_debounce_key("retry", message_id)
        if existing_debounced := self._find_debounced_action(session, cocoon_id, "retry", debounce_key):
            return existing_debounced
        action = ActionDispatch(
            cocoon_id=cocoon_id,
            event_type="retry",
            status=ActionStatus.queued,
            debounce_until=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=self.debounce_seconds),
            payload_json={"message_id": message_id, "debounce_key": debounce_key},
        )
        session.add(action)
        session.flush()
        queue_length = self.chat_queue.enqueue(action.id, cocoon_id, "retry", action.payload_json)
        self.realtime_hub.publish(
            cocoon_id,
            {"type": "dispatch_queued", "action_id": action.id, "queue_length": queue_length},
        )
        return action
