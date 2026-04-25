"""Message window subservice for runtime context assembly."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message, MessageTag, TagRegistry
from app.services.catalog.tag_policy import is_tag_visible_in_target
from app.services.workspace.targets import build_target_filter


class MessageWindowService:
    """Collects the message window visible to a runtime round."""

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

    def list_visible_messages(
        self,
        session: Session,
        max_context_messages: int,
        active_tags: list[str],
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        context_start_message_id: str | None = None,
    ) -> list[Message]:
        """Return the recent message window, filtered by active tags when present."""
        if cocoon_id and context_start_message_id:
            all_messages = list(
                session.scalars(
                    select(Message)
                    .where(build_target_filter(Message, cocoon_id=cocoon_id, chat_group_id=chat_group_id))
                    .order_by(Message.created_at.asc())
                ).all()
            )
            visible_messages = self._trim_to_context_start(all_messages, context_start_message_id)[
                -max_context_messages:
            ]
        else:
            visible_messages = list(
                session.scalars(
                    select(Message)
                    .where(build_target_filter(Message, cocoon_id=cocoon_id, chat_group_id=chat_group_id))
                    .order_by(Message.created_at.desc())
                    .limit(max_context_messages)
                ).all()
            )
            visible_messages.reverse()
        if chat_group_id:
            tags = {
                tag.id: tag
                for tag in session.scalars(select(TagRegistry)).all()
            }
            visible_messages = [
                message
                for message in visible_messages
                if all(
                    (
                        tag_id not in tags
                        or is_tag_visible_in_target(
                            session,
                            tags[tag_id],
                            target_type="chat_group",
                            target_id=chat_group_id,
                        )
                    )
                    for tag_id in (message.tags_json or [])
                )
            ]
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
