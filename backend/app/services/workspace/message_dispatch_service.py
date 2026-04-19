"""Workspace message/action dispatch orchestration service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionDispatch, ChatGroupRoom, Cocoon, Message, MessageTag
from app.models.entities import ActionStatus
from app.services.catalog.system_settings_service import SystemSettingsService
from app.services.jobs.chat_dispatch import ChatDispatchQueue
from app.services.realtime.hub import RealtimeHub
from app.services.runtime.wakeup_tasks import cancel_wakeup_tasks
from app.services.workspace.targets import ensure_session_state, target_channel_key


class MessageDispatchService:
    """Creates message-related action dispatches and publishes queue events."""

    DEFAULT_DEBOUNCE_SECONDS = 2

    def __init__(
        self,
        chat_queue: ChatDispatchQueue,
        realtime_hub: RealtimeHub,
        system_settings_service: SystemSettingsService | None = None,
        debounce_seconds: int | None = None,
    ) -> None:
        self.chat_queue = chat_queue
        self.realtime_hub = realtime_hub
        self.system_settings_service = system_settings_service
        self.debounce_seconds = debounce_seconds or self.DEFAULT_DEBOUNCE_SECONDS

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
        filters = [ActionDispatch.event_type == event_type, ActionDispatch.debounce_until.is_not(None), ActionDispatch.debounce_until > now]
        if cocoon_id:
            filters.extend([ActionDispatch.cocoon_id == cocoon_id, ActionDispatch.chat_group_id.is_(None)])
        if chat_group_id:
            filters.extend([ActionDispatch.chat_group_id == chat_group_id, ActionDispatch.cocoon_id.is_(None)])
        candidates = list(
            session.scalars(
                select(ActionDispatch)
                .where(*filters)
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
        channel_key = target_channel_key(cocoon_id=cocoon_id, chat_group_id=chat_group_id)
        self.realtime_hub.publish(
            channel_key,
            {"type": "dispatch_queued", "action_id": action.id, "queue_length": queue_length},
        )

    def enqueue_chat_message(
        self,
        session: Session,
        cocoon_id: str,
        *,
        content: str,
        client_request_id: str,
        timezone: str,
        client_sent_at: datetime | None = None,
        locale: str | None = None,
        idle_seconds: int | None = None,
        recent_turn_count: int | None = None,
        typing_hint_ms: int | None = None,
        sender_user_id: str | None = None,
    ) -> ActionDispatch:
        """Create a chat action and user message, enqueue it, and emit a queue event."""
        existing = session.scalar(
            select(ActionDispatch).where(ActionDispatch.client_request_id == client_request_id)
        )
        if existing:
            return existing
        debounce_key = self._build_debounce_key("chat", content)
        if existing_debounced := self._find_debounced_action(
            session,
            cocoon_id=cocoon_id,
            event_type="chat",
            debounce_key=debounce_key,
        ):
            return existing_debounced

        cocoon = session.get(Cocoon, cocoon_id)
        if not cocoon:
            raise ValueError("Cocoon not found")
        state = ensure_session_state(session, cocoon_id=cocoon_id)
        cancel_wakeup_tasks(
            session,
            cocoon_id=cocoon_id,
            only_trigger_kind="idle_timeout",
            cancelled_reason="Cancelled because the user sent a new message",
        )
        debounce_seconds = self._current_debounce_seconds(session)

        action = ActionDispatch(
            cocoon_id=cocoon_id,
            event_type="chat",
            status=ActionStatus.queued,
            client_request_id=client_request_id,
            debounce_until=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=debounce_seconds),
            payload_json={
                "timezone": timezone,
                "debounce_key": debounce_key,
                "client_sent_at": client_sent_at.isoformat() if client_sent_at else None,
                "locale": locale,
                "idle_seconds": idle_seconds,
                "recent_turn_count": recent_turn_count,
                "typing_hint_ms": typing_hint_ms,
            },
        )
        session.add(action)
        session.flush()

        message = Message(
            cocoon_id=cocoon_id,
            action_id=action.id,
            client_request_id=client_request_id,
            sender_user_id=sender_user_id,
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
            "client_sent_at": client_sent_at.isoformat() if client_sent_at else None,
            "locale": locale,
            "idle_seconds": idle_seconds,
            "recent_turn_count": recent_turn_count,
            "typing_hint_ms": typing_hint_ms,
        }
        for tag in state.active_tags_json:
            session.add(MessageTag(message_id=message.id, tag_id=tag))
        session.flush()
        self._commit_then_enqueue(
            session,
            action=action,
            cocoon_id=cocoon_id,
            event_type="chat",
            payload=dict(action.payload_json),
        )
        return action

    def enqueue_chat_group_message(
        self,
        session: Session,
        chat_group_id: str,
        *,
        content: str,
        client_request_id: str,
        timezone: str,
        client_sent_at: datetime | None = None,
        locale: str | None = None,
        idle_seconds: int | None = None,
        recent_turn_count: int | None = None,
        typing_hint_ms: int | None = None,
        sender_user_id: str,
    ) -> ActionDispatch:
        existing = session.scalar(
            select(ActionDispatch).where(ActionDispatch.client_request_id == client_request_id)
        )
        if existing:
            return existing
        debounce_key = self._build_debounce_key("chat_group", chat_group_id, sender_user_id, content)
        if existing_debounced := self._find_debounced_action(
            session,
            chat_group_id=chat_group_id,
            event_type="chat",
            debounce_key=debounce_key,
        ):
            return existing_debounced

        room = session.get(ChatGroupRoom, chat_group_id)
        if not room:
            raise ValueError("Chat group room not found")
        state = ensure_session_state(session, chat_group_id=chat_group_id)
        cancel_wakeup_tasks(
            session,
            chat_group_id=chat_group_id,
            only_trigger_kind="idle_timeout",
            cancelled_reason="Cancelled because the user sent a new group message",
        )
        debounce_seconds = self._current_debounce_seconds(session)

        action = ActionDispatch(
            chat_group_id=chat_group_id,
            event_type="chat",
            status=ActionStatus.queued,
            client_request_id=client_request_id,
            debounce_until=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=debounce_seconds),
            payload_json={
                "timezone": timezone,
                "debounce_key": debounce_key,
                "sender_user_id": sender_user_id,
                "character_id": room.character_id,
                "client_sent_at": client_sent_at.isoformat() if client_sent_at else None,
                "locale": locale,
                "idle_seconds": idle_seconds,
                "recent_turn_count": recent_turn_count,
                "typing_hint_ms": typing_hint_ms,
            },
        )
        session.add(action)
        session.flush()

        message = Message(
            chat_group_id=chat_group_id,
            action_id=action.id,
            client_request_id=client_request_id,
            sender_user_id=sender_user_id,
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
            "sender_user_id": sender_user_id,
            "character_id": room.character_id,
            "client_sent_at": client_sent_at.isoformat() if client_sent_at else None,
            "locale": locale,
            "idle_seconds": idle_seconds,
            "recent_turn_count": recent_turn_count,
            "typing_hint_ms": typing_hint_ms,
        }
        for tag in state.active_tags_json:
            session.add(MessageTag(message_id=message.id, tag_id=tag))
        session.flush()
        self._commit_then_enqueue(
            session,
            action=action,
            chat_group_id=chat_group_id,
            event_type="chat",
            payload=dict(action.payload_json),
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
        if existing_debounced := self._find_debounced_action(
            session,
            cocoon_id=cocoon_id,
            event_type="edit",
            debounce_key=debounce_key,
        ):
            return existing_debounced
        message.content = content
        debounce_seconds = self._current_debounce_seconds(session)
        action = ActionDispatch(
            cocoon_id=cocoon_id,
            event_type="edit",
            status=ActionStatus.queued,
            debounce_until=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=debounce_seconds),
            payload_json={"message_id": message.id, "debounce_key": debounce_key},
        )
        session.add(action)
        session.flush()
        self._commit_then_enqueue(
            session,
            action=action,
            cocoon_id=cocoon_id,
            event_type="edit",
            payload=dict(action.payload_json),
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
        if existing_debounced := self._find_debounced_action(
            session,
            cocoon_id=cocoon_id,
            event_type="retry",
            debounce_key=debounce_key,
        ):
            return existing_debounced
        debounce_seconds = self._current_debounce_seconds(session)
        action = ActionDispatch(
            cocoon_id=cocoon_id,
            event_type="retry",
            status=ActionStatus.queued,
            debounce_until=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=debounce_seconds),
            payload_json={"message_id": message_id, "debounce_key": debounce_key},
        )
        session.add(action)
        session.flush()
        self._commit_then_enqueue(
            session,
            action=action,
            cocoon_id=cocoon_id,
            event_type="retry",
            payload=dict(action.payload_json),
        )
        return action
