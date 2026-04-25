"""Tag catalog administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChatGroupTagBinding,
    CocoonTagBinding,
    MemoryChunk,
    MemoryTag,
    Message,
    MessageTag,
    SessionState,
    TagChatGroupVisibility,
    TagRegistry,
)
from app.schemas.catalog.tags import TagCreate, TagOut, TagUpdate
from app.services.catalog.tag_policy import (
    is_system_tag,
    list_visible_chat_group_ids,
    replace_tag_visibility_groups,
    require_canonical_tag,
    require_valid_visibility,
)


class TagService:
    """Creates, lists, and updates tag definitions."""

    def _get_tag(self, session: Session, tag_ref: str) -> TagRegistry | None:
        tag = session.get(TagRegistry, tag_ref)
        if tag:
            return tag
        return session.scalar(select(TagRegistry).where(TagRegistry.tag_id == tag_ref))

    def list_tags(self, session: Session) -> list[TagRegistry]:
        """Return tags ordered by tag id."""
        return list(session.scalars(select(TagRegistry).order_by(TagRegistry.tag_id.asc())).all())

    def serialize_tag(self, session: Session, tag: TagRegistry) -> TagOut:
        return TagOut.model_validate(
            {
                "id": tag.id,
                "tag_id": tag.tag_id,
                "brief": tag.brief,
                "visibility": require_valid_visibility(tag.visibility),
                "is_isolated": bool(tag.is_isolated),
                "is_system": is_system_tag(tag),
                "meta_json": tag.meta_json or {},
                "visible_chat_group_ids": list_visible_chat_group_ids(session, tag.id),
                "created_at": tag.created_at,
            }
        )

    def create_tag(self, session: Session, payload: TagCreate) -> TagRegistry:
        """Create a tag registry entry."""
        visibility = require_valid_visibility(payload.visibility)
        tag = TagRegistry(
            tag_id=payload.tag_id,
            brief=payload.brief,
            visibility=visibility,
            is_isolated=payload.is_isolated or visibility == "private",
            is_system=False,
            meta_json=payload.meta_json or {},
        )
        session.add(tag)
        session.flush()
        replace_tag_visibility_groups(session, tag, payload.visible_chat_group_ids)
        return tag

    def update_tag(self, session: Session, tag_id: str, payload: TagUpdate) -> TagRegistry:
        """Patch a tag registry entry."""
        tag = self._get_tag(session, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        if is_system_tag(tag):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System tag cannot be modified")
        if payload.brief is not None:
            tag.brief = payload.brief
        if payload.visibility is not None:
            tag.visibility = require_valid_visibility(payload.visibility)
            tag.is_isolated = tag.visibility == "private" if payload.is_isolated is None else payload.is_isolated
        if payload.is_isolated is not None:
            tag.is_isolated = payload.is_isolated
        if payload.meta_json is not None:
            tag.meta_json = payload.meta_json
        if payload.visible_chat_group_ids is not None:
            replace_tag_visibility_groups(session, tag, payload.visible_chat_group_ids)
        session.flush()
        return tag

    def delete_tag(self, session: Session, tag_id: str) -> TagRegistry:
        """Delete a tag and scrub all bindings and cached tag arrays."""
        tag = require_canonical_tag(session, tag_id)
        if is_system_tag(tag):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System tag cannot be deleted")

        session.query(CocoonTagBinding).filter(CocoonTagBinding.tag_id == tag.id).delete(synchronize_session=False)
        session.query(ChatGroupTagBinding).filter(ChatGroupTagBinding.tag_id == tag.id).delete(
            synchronize_session=False
        )
        session.query(TagChatGroupVisibility).filter(TagChatGroupVisibility.tag_id == tag.id).delete(
            synchronize_session=False
        )
        session.query(MessageTag).filter(MessageTag.tag_id == tag.id).delete(synchronize_session=False)
        session.query(MemoryTag).filter(MemoryTag.tag_id == tag.id).delete(synchronize_session=False)

        for state in session.scalars(select(SessionState)).all():
            if tag.id in (state.active_tags_json or []):
                state.active_tags_json = [item for item in state.active_tags_json if item != tag.id]

        for message in session.scalars(select(Message).where(Message.tags_json.is_not(None))).all():
            if tag.id in (message.tags_json or []):
                message.tags_json = [item for item in message.tags_json if item != tag.id]

        for memory in session.scalars(select(MemoryChunk).where(MemoryChunk.tags_json.is_not(None))).all():
            if tag.id in (memory.tags_json or []):
                memory.tags_json = [item for item in memory.tags_json if item != tag.id]

        session.delete(tag)
        session.flush()
        return tag
