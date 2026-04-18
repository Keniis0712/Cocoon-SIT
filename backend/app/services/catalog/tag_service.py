"""Tag catalog administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TagRegistry
from app.schemas.catalog.tags import TagCreate, TagUpdate


class TagService:
    """Creates, lists, and updates tag definitions."""

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
        tag = session.scalar(select(TagRegistry).where(TagRegistry.tag_id == tag_id))
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
