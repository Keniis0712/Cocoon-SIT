"""Tag catalog administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CocoonTagBinding, MemoryChunk, MemoryTag, Message, MessageTag, SessionState, TagRegistry
from app.schemas.catalog.tags import TagCreate, TagUpdate


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

    def create_tag(self, session: Session, payload: TagCreate) -> TagRegistry:
        """Create a tag registry entry."""
        tag = TagRegistry(
            tag_id=payload.tag_id,
            brief=payload.brief,
            is_isolated=payload.is_isolated,
            meta_json=payload.meta_json,
        )
        session.add(tag)
        session.flush()
        return tag

    def update_tag(self, session: Session, tag_id: str, payload: TagUpdate) -> TagRegistry:
        """Patch a tag registry entry."""
        tag = self._get_tag(session, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        if payload.brief is not None:
            tag.brief = payload.brief
        if payload.is_isolated is not None:
            tag.is_isolated = payload.is_isolated
        if payload.meta_json is not None:
            tag.meta_json = payload.meta_json
        session.flush()
        return tag

    def delete_tag(self, session: Session, tag_id: str) -> TagRegistry:
        """Delete a tag and scrub all bindings and cached tag arrays."""
        tag = self._get_tag(session, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

        session.query(CocoonTagBinding).filter(CocoonTagBinding.tag_id == tag.id).delete(synchronize_session=False)
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
