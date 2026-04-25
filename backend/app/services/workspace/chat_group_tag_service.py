"""Workspace chat-group tag binding service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatGroupTagBinding
from app.services.catalog.tag_policy import (
    canonicalize_tag_refs,
    ensure_target_default_binding,
    is_system_tag,
    require_canonical_tag,
    resolve_tag_owner_user_id_for_target,
)
from app.services.workspace.targets import get_session_state


class ChatGroupTagService:
    """Applies chat-group tag bindings and keeps session state tags aligned."""

    def bind_tag(self, session: Session, chat_group_id: str, tag_id: str) -> ChatGroupTagBinding:
        owner_user_id = resolve_tag_owner_user_id_for_target(session, chat_group_id=chat_group_id)
        tag = require_canonical_tag(session, tag_id, owner_user_id=owner_user_id)
        ensure_target_default_binding(session, chat_group_id=chat_group_id)
        existing = session.scalar(
            select(ChatGroupTagBinding).where(
                ChatGroupTagBinding.chat_group_id == chat_group_id,
                ChatGroupTagBinding.tag_id == tag.id,
            )
        )
        if existing:
            return existing
        binding = ChatGroupTagBinding(chat_group_id=chat_group_id, tag_id=tag.id)
        session.add(binding)
        state = get_session_state(session, chat_group_id=chat_group_id)
        if state and tag.id not in state.active_tags_json:
            state.active_tags_json = canonicalize_tag_refs(
                session,
                [*state.active_tags_json, tag.id],
                include_default=True,
                owner_user_id=owner_user_id,
            )
        session.flush()
        return binding

    def unbind_tag(self, session: Session, chat_group_id: str, tag_id: str) -> ChatGroupTagBinding:
        owner_user_id = resolve_tag_owner_user_id_for_target(session, chat_group_id=chat_group_id)
        tag = require_canonical_tag(session, tag_id, owner_user_id=owner_user_id)
        if is_system_tag(tag):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System tag cannot be unbound")
        binding = session.scalar(
            select(ChatGroupTagBinding).where(
                ChatGroupTagBinding.chat_group_id == chat_group_id,
                ChatGroupTagBinding.tag_id == tag.id,
            )
        )
        if not binding:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag binding not found")
        state = get_session_state(session, chat_group_id=chat_group_id)
        if state:
            state.active_tags_json = canonicalize_tag_refs(
                session,
                [item for item in state.active_tags_json if item != tag.id],
                include_default=True,
                owner_user_id=owner_user_id,
            )
        session.delete(binding)
        session.flush()
        return binding
