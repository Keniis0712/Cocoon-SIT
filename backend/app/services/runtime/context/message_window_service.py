"""Message window subservice for runtime context assembly."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message, MessageTag


class MessageWindowService:
    """Collects the message window visible to a runtime round."""

    def list_visible_messages(
        self,
        session: Session,
        cocoon_id: str,
        max_context_messages: int,
        active_tags: list[str],
    ) -> list[Message]:
        """Return the recent message window, filtered by active tags when present."""
        visible_messages = list(
            session.scalars(
                select(Message)
                .where(Message.cocoon_id == cocoon_id)
                .order_by(Message.created_at.desc())
                .limit(max_context_messages)
            ).all()
        )
        visible_messages.reverse()
        if not active_tags:
            return visible_messages

        tagged_ids = {
            item.message_id
            for item in session.scalars(select(MessageTag).where(MessageTag.tag_id.in_(active_tags))).all()
        }
        filtered = [
            message
            for message in visible_messages
            if not message.tags_json
            or message.id in tagged_ids
            or set(message.tags_json).intersection(active_tags)
        ]
        return filtered or visible_messages
