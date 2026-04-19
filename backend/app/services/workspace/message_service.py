"""Shared message querying and mutation helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message
from app.schemas.workspace.cocoons import ChatMessageOut
from app.services.workspace.targets import build_target_filter


class MessageService:
    """Lists and mutates stored conversation messages."""

    RETRACTED_PLACEHOLDER = "[message retracted]"

    def list_messages(
        self,
        session: Session,
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
    ) -> list[Message]:
        return list(
            session.scalars(
                select(Message)
                .where(build_target_filter(Message, cocoon_id=cocoon_id, chat_group_id=chat_group_id))
                .order_by(Message.created_at.asc())
            ).all()
        )

    def serialize_message(self, message: Message) -> ChatMessageOut:
        content = self.RETRACTED_PLACEHOLDER if message.is_retracted else message.content
        return ChatMessageOut(
            id=message.id,
            cocoon_id=message.cocoon_id,
            chat_group_id=message.chat_group_id,
            action_id=message.action_id,
            client_request_id=message.client_request_id,
            sender_user_id=message.sender_user_id,
            role=message.role,
            content=content,
            is_thought=message.is_thought,
            is_retracted=message.is_retracted,
            retracted_at=message.retracted_at,
            retracted_by_user_id=message.retracted_by_user_id,
            retraction_note=message.retraction_note,
            tags_json=message.tags_json,
            created_at=message.created_at,
        )

    def retract_message(self, session: Session, message: Message, *, acting_user_id: str, note: str | None) -> Message:
        if message.is_retracted:
            return message
        message.is_retracted = True
        message.retracted_at = datetime.now(UTC).replace(tzinfo=None)
        message.retracted_by_user_id = acting_user_id
        message.retraction_note = note or "Message retracted"
        session.flush()
        return message

    def require_message_for_target(
        self,
        session: Session,
        message_id: str,
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
    ) -> Message:
        message = session.get(Message, message_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        if cocoon_id and message.cocoon_id != cocoon_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        if chat_group_id and message.chat_group_id != chat_group_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        return message
