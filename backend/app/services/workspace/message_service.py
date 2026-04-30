"""Shared message querying and mutation helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import Message
from app.schemas.workspace.cocoons import ChatMessageOut
from app.services.workspace.targets import build_target_filter
from app.services.workspace.targets import list_cocoon_lineage


class MessageService:
    """Lists and mutates stored conversation messages."""

    RETRACTED_PLACEHOLDER = "[message retracted]"

    def _trim_to_context_start(
        self,
        messages: list[Message],
        context_start_message_id: str | None,
    ) -> list[Message]:
        if not context_start_message_id:
            return messages
        for index, message in enumerate(messages):
            if message.id == context_start_message_id:
                return messages[index:]
        return messages

    def _list_cocoon_lineage_messages(self, session: Session, cocoon_id: str) -> list[Message]:
        lineage = list_cocoon_lineage(session, cocoon_id)
        if not lineage:
            return list(
                session.scalars(
                    select(Message)
                    .where(Message.cocoon_id == cocoon_id)
                    .order_by(Message.created_at.asc(), Message.id.asc())
                ).all()
            )

        cocoon_ids = [item.id for item in lineage]
        all_messages = list(
            session.scalars(
                select(Message)
                .where(Message.cocoon_id.in_(cocoon_ids))
                .order_by(Message.created_at.asc(), Message.id.asc())
            ).all()
        )
        messages_by_cocoon: dict[str, list[Message]] = {item.id: [] for item in lineage}
        for message in all_messages:
            if message.cocoon_id in messages_by_cocoon:
                messages_by_cocoon[message.cocoon_id].append(message)

        visible_messages: list[Message] = []
        for cocoon in lineage:
            visible_messages.extend(
                self._trim_to_context_start(messages_by_cocoon.get(cocoon.id, []), cocoon.context_start_message_id)
            )
        return visible_messages

    def list_messages(
        self,
        session: Session,
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        before_message_id: str | None = None,
        limit: int | None = None,
    ) -> list[Message]:
        if cocoon_id:
            messages = self._list_cocoon_lineage_messages(session, cocoon_id)
            if before_message_id:
                anchor = session.get(Message, before_message_id)
                if not anchor or anchor.cocoon_id not in {item.cocoon_id for item in messages}:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
                messages = [
                    message
                    for message in messages
                    if (message.created_at, message.id) < (anchor.created_at, anchor.id)
                ]
            if limit is not None:
                return messages[-limit:]
            return messages

        target_filter = build_target_filter(Message, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
        query = select(Message).where(target_filter)

        if before_message_id:
            anchor = self.require_message_for_target(
                session,
                before_message_id,
                cocoon_id=cocoon_id,
                chat_group_id=chat_group_id,
            )
            query = query.where(
                or_(
                    Message.created_at < anchor.created_at,
                    and_(Message.created_at == anchor.created_at, Message.id < anchor.id),
                )
            )

        if limit is not None:
            messages = list(
                session.scalars(
                    query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
                ).all()
            )
            messages.reverse()
            return messages

        return list(session.scalars(query.order_by(Message.created_at.asc(), Message.id.asc())).all())

    def serialize_message(self, message: Message) -> ChatMessageOut:
        content = self.RETRACTED_PLACEHOLDER if message.is_retracted else message.content
        return ChatMessageOut(
            id=message.id,
            cocoon_id=message.cocoon_id,
            chat_group_id=message.chat_group_id,
            action_id=message.action_id,
            client_request_id=message.client_request_id,
            sender_user_id=message.sender_user_id,
            external_sender_id=message.external_sender_id,
            external_sender_display_name=message.external_sender_display_name,
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
