"""Workspace message/action dispatch orchestration service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ActionDispatch, ChatGroupRoom, Cocoon, Message, MessageTag
from app.models.entities import ActionStatus
from app.services.catalog.system_settings_service import SystemSettingsService
from app.services.jobs.chat_dispatch import ChatDispatchQueue
from app.services.realtime.hub import RealtimeHub
from app.services.runtime.scheduling.wakeup_tasks import cancel_wakeup_tasks
from app.services.workspace.message_dispatch_base import MessageDispatchBase
from app.services.workspace.targets import ensure_session_state


class MessageDispatchService(MessageDispatchBase):
    """Creates message-related action dispatches and publishes queue events."""

    DEFAULT_DEBOUNCE_SECONDS = 2

    logger = logging.getLogger(__name__)

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

    def enqueue_chat_message(
        self,
        session: Session,
        cocoon_id: str,
        *,
        content: str,
        client_request_id: str,
        timezone: str | None,
        client_sent_at: datetime | None = None,
        locale: str | None = None,
        idle_seconds: int | None = None,
        recent_turn_count: int | None = None,
        typing_hint_ms: int | None = None,
        sender_user_id: str | None = None,
        external_sender_id: str | None = None,
        external_sender_display_name: str | None = None,
        extra_payload: dict | None = None,
    ) -> ActionDispatch:
        """Create a chat action and user message, enqueue it, and emit a queue event."""
        timezone_name = (timezone or "UTC").strip() or "UTC"
        existing = self._find_action_for_client_request_id(session, client_request_id)
        if existing:
            self.logger.info(
                "Reusing existing chat action_id=%s for client_request_id=%s cocoon_id=%s",
                existing.id,
                client_request_id,
                cocoon_id,
            )
            return existing

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
        debounce_seconds = self._current_debounce_seconds(session, target_type="cocoon")
        now = datetime.now(UTC).replace(tzinfo=None)
        debounce_until = now + timedelta(seconds=debounce_seconds)
        pending_action = (
            self._find_pending_chat_action(session, cocoon_id=cocoon_id)
            if debounce_seconds > 0
            else None
        )
        if pending_action:
            self.logger.info(
                "Aggregating chat message into pending action_id=%s cocoon_id=%s",
                pending_action.id,
                cocoon_id,
            )
        debounce_key = self._build_debounce_key("chat", cocoon_id)

        action = pending_action
        if action is None:
            action = ActionDispatch(
                cocoon_id=cocoon_id,
                event_type="chat",
                status=ActionStatus.queued,
                client_request_id=client_request_id,
                debounce_until=debounce_until,
                payload_json={
                    "timezone": timezone_name,
                    "debounce_key": debounce_key,
                    "chat_retry_attempt": 1,
                    "client_sent_at": client_sent_at.isoformat() if client_sent_at else None,
                    "locale": locale,
                    "idle_seconds": idle_seconds,
                    "recent_turn_count": recent_turn_count,
                    "typing_hint_ms": typing_hint_ms,
                    "aggregated_message_count": 0,
                    **dict(extra_payload or {}),
                },
            )
            session.add(action)
            session.flush()
        else:
            action.debounce_until = debounce_until

        message = Message(
            cocoon_id=cocoon_id,
            action_id=action.id,
            client_request_id=client_request_id,
            sender_user_id=sender_user_id,
            external_sender_id=external_sender_id,
            external_sender_display_name=external_sender_display_name,
            role="user",
            content=content,
            tags_json=state.active_tags_json,
        )
        session.add(message)
        session.flush()
        action.payload_json = {
            "message_id": message.id,
            "client_request_id": action.client_request_id or client_request_id,
            "timezone": timezone_name,
            "debounce_key": debounce_key,
            "chat_retry_attempt": int((action.payload_json or {}).get("chat_retry_attempt") or 1),
            "client_sent_at": client_sent_at.isoformat() if client_sent_at else None,
            "locale": locale,
            "idle_seconds": idle_seconds,
            "recent_turn_count": recent_turn_count,
            "typing_hint_ms": typing_hint_ms,
            "sender_user_id": sender_user_id,
            "external_sender_id": external_sender_id,
            "external_sender_display_name": external_sender_display_name,
            "aggregated_message_count": self._count_action_messages(session, action.id),
            **dict(extra_payload or {}),
        }
        for tag in state.active_tags_json:
            session.add(MessageTag(message_id=message.id, tag_id=tag))
        session.flush()
        if pending_action is None:
            self._commit_then_enqueue(
                session,
                action=action,
                cocoon_id=cocoon_id,
                event_type="chat",
                payload=dict(action.payload_json),
            )
        else:
            session.commit()
        return action

    def enqueue_chat_group_message(
        self,
        session: Session,
        chat_group_id: str,
        *,
        content: str,
        client_request_id: str,
        timezone: str | None,
        client_sent_at: datetime | None = None,
        locale: str | None = None,
        idle_seconds: int | None = None,
        recent_turn_count: int | None = None,
        typing_hint_ms: int | None = None,
        sender_user_id: str | None,
        external_sender_id: str | None = None,
        external_sender_display_name: str | None = None,
        extra_payload: dict | None = None,
    ) -> ActionDispatch:
        timezone_name = (timezone or "UTC").strip() or "UTC"
        existing = self._find_action_for_client_request_id(session, client_request_id)
        if existing:
            self.logger.info(
                "Reusing existing chat-group action_id=%s for client_request_id=%s "
                "chat_group_id=%s",
                existing.id,
                client_request_id,
                chat_group_id,
            )
            return existing

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
        debounce_seconds = self._current_debounce_seconds(session, target_type="chat_group")
        now = datetime.now(UTC).replace(tzinfo=None)
        debounce_until = now + timedelta(seconds=debounce_seconds)
        pending_action = (
            self._find_pending_chat_action(session, chat_group_id=chat_group_id)
            if debounce_seconds > 0
            else None
        )
        if pending_action:
            self.logger.info(
                "Aggregating chat-group message into pending action_id=%s chat_group_id=%s",
                pending_action.id,
                chat_group_id,
            )
        debounce_key = self._build_debounce_key("chat_group", chat_group_id)

        action = pending_action
        if action is None:
            action = ActionDispatch(
                chat_group_id=chat_group_id,
                event_type="chat",
                status=ActionStatus.queued,
                client_request_id=client_request_id,
                debounce_until=debounce_until,
                payload_json={
                    "timezone": timezone_name,
                    "debounce_key": debounce_key,
                    "chat_retry_attempt": 1,
                    "sender_user_id": sender_user_id,
                    "external_sender_id": external_sender_id,
                    "external_sender_display_name": external_sender_display_name,
                    "character_id": room.character_id,
                    "client_sent_at": client_sent_at.isoformat() if client_sent_at else None,
                    "locale": locale,
                    "idle_seconds": idle_seconds,
                    "recent_turn_count": recent_turn_count,
                    "typing_hint_ms": typing_hint_ms,
                    "aggregated_message_count": 0,
                    **dict(extra_payload or {}),
                },
            )
            session.add(action)
            session.flush()
        else:
            action.debounce_until = debounce_until

        message = Message(
            chat_group_id=chat_group_id,
            action_id=action.id,
            client_request_id=client_request_id,
            sender_user_id=sender_user_id,
            external_sender_id=external_sender_id,
            external_sender_display_name=external_sender_display_name,
            role="user",
            content=content,
            tags_json=state.active_tags_json,
        )
        session.add(message)
        session.flush()
        action.payload_json = {
            "message_id": message.id,
            "client_request_id": action.client_request_id or client_request_id,
            "timezone": timezone_name,
            "debounce_key": debounce_key,
            "chat_retry_attempt": int((action.payload_json or {}).get("chat_retry_attempt") or 1),
            "sender_user_id": sender_user_id,
            "external_sender_id": external_sender_id,
            "external_sender_display_name": external_sender_display_name,
            "character_id": room.character_id,
            "client_sent_at": client_sent_at.isoformat() if client_sent_at else None,
            "locale": locale,
            "idle_seconds": idle_seconds,
            "recent_turn_count": recent_turn_count,
            "typing_hint_ms": typing_hint_ms,
            "aggregated_message_count": self._count_action_messages(session, action.id),
            **dict(extra_payload or {}),
        }
        for tag in state.active_tags_json:
            session.add(MessageTag(message_id=message.id, tag_id=tag))
        session.flush()
        if pending_action is None:
            self._commit_then_enqueue(
                session,
                action=action,
                chat_group_id=chat_group_id,
                event_type="chat",
                payload=dict(action.payload_json),
            )
        else:
            session.commit()
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
            debounce_until=datetime.now(UTC).replace(tzinfo=None)
            + timedelta(seconds=debounce_seconds),
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
            debounce_until=datetime.now(UTC).replace(tzinfo=None)
            + timedelta(seconds=debounce_seconds),
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

    def _count_action_messages(self, session: Session, action_id: str) -> int:
        return int(
            session.scalar(select(func.count()).select_from(Message).where(Message.action_id == action_id))
            or 0
        )
