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
    User,
)
from app.schemas.catalog.tags import TagCreate, TagOut, TagUpdate
from app.services.catalog.tag_policy import (
    canonicalize_tag_refs,
    is_system_tag,
    list_tags_for_user,
    list_visible_chat_group_ids,
    replace_tag_visibility_groups,
    require_canonical_tag,
    require_valid_visibility,
    resolve_tag_owner_user_id_for_state,
)


class TagService:
    """Creates, lists, and updates user-owned private tag definitions."""

    def _get_tag(self, session: Session, user: User, tag_ref: str) -> TagRegistry | None:
        tag = require_canonical_tag(session, tag_ref, owner_user_id=user.id)
        return tag if tag.owner_user_id == user.id else None

    def list_tags(self, session: Session, user: User) -> list[TagRegistry]:
        """Return the current user's tags ordered by system-then-name."""
        return list_tags_for_user(session, user.id)

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

    def create_tag(self, session: Session, user: User, payload: TagCreate) -> TagRegistry:
        """Create a private tag owned by the current user."""
        normalized_tag_id = str(payload.tag_id or "").strip()
        if not normalized_tag_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag name is required")
        if normalized_tag_id == "default":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reserved system tag name")
        require_valid_visibility(payload.visibility)
        existing = session.scalar(
            select(TagRegistry).where(
                TagRegistry.owner_user_id == user.id,
                TagRegistry.tag_id == normalized_tag_id,
            )
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag already exists")
        tag = TagRegistry(
            owner_user_id=user.id,
            tag_id=normalized_tag_id,
            brief=payload.brief,
            visibility="private",
            is_isolated=True,
            is_system=False,
            is_hidden=False,
            meta_json=payload.meta_json or {},
        )
        session.add(tag)
        session.flush()
        replace_tag_visibility_groups(session, tag, [])
        return tag

    def update_tag(self, session: Session, user: User, tag_id: str, payload: TagUpdate) -> TagRegistry:
        """Patch a user-owned private tag."""
        tag = self._get_tag(session, user, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        if is_system_tag(tag):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System tag cannot be modified")
        if payload.visibility is not None:
            require_valid_visibility(payload.visibility)
        if payload.brief is not None:
            tag.brief = payload.brief
        tag.visibility = "private"
        tag.is_isolated = True
        if payload.meta_json is not None:
            tag.meta_json = payload.meta_json
        if payload.visible_chat_group_ids is not None:
            replace_tag_visibility_groups(session, tag, payload.visible_chat_group_ids)
        session.flush()
        return tag

    def delete_tag(self, session: Session, user: User, tag_id: str) -> TagRegistry:
        """Delete a user-owned tag and scrub all bindings and cached tag arrays."""
        tag = self._get_tag(session, user, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
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
                owner_user_id = resolve_tag_owner_user_id_for_state(session, state)
                state.active_tags_json = canonicalize_tag_refs(
                    session,
                    [item for item in state.active_tags_json if item != tag.id],
                    include_default=True,
                    owner_user_id=owner_user_id,
                )

        for message in session.scalars(select(Message).where(Message.tags_json.is_not(None))).all():
            if tag.id in (message.tags_json or []):
                message.tags_json = [item for item in message.tags_json if item != tag.id]

        for memory in session.scalars(select(MemoryChunk).where(MemoryChunk.tags_json.is_not(None))).all():
            if tag.id in (memory.tags_json or []):
                memory.tags_json = [item for item in memory.tags_json if item != tag.id]

        session.delete(tag)
        session.flush()
        return tag
