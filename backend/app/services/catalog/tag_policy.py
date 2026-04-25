"""Shared tag policy helpers for canonical ids, default bindings, and target visibility."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChatGroupRoom,
    ChatGroupTagBinding,
    Cocoon,
    CocoonTagBinding,
    MemoryChunk,
    MemoryTag,
    Message,
    MessageTag,
    SessionState,
    TagChatGroupVisibility,
    TagRegistry,
)

DEFAULT_TAG_SLUG = "default"
TAG_VISIBILITY_PUBLIC = "public"
TAG_VISIBILITY_PRIVATE = "private"
TAG_VISIBILITY_GROUP_ACL = "group_acl"
VALID_TAG_VISIBILITIES = {
    TAG_VISIBILITY_PUBLIC,
    TAG_VISIBILITY_PRIVATE,
    TAG_VISIBILITY_GROUP_ACL,
}


def is_system_tag(tag: TagRegistry | None) -> bool:
    if tag is None:
        return False
    return bool(tag.is_system or str(tag.tag_id or "").strip() == DEFAULT_TAG_SLUG)


def ensure_default_tag(session: Session) -> TagRegistry:
    tag = session.scalar(select(TagRegistry).where(TagRegistry.tag_id == DEFAULT_TAG_SLUG))
    if tag:
        tag.visibility = TAG_VISIBILITY_PUBLIC
        tag.is_isolated = False
        tag.is_system = True
        tag.meta_json = {**(tag.meta_json or {}), "system": True}
        session.flush()
        return tag
    tag = TagRegistry(
        tag_id=DEFAULT_TAG_SLUG,
        brief="Default memory boundary automatically applied to every target.",
        visibility=TAG_VISIBILITY_PUBLIC,
        is_isolated=False,
        is_system=True,
        meta_json={"system": True},
    )
    session.add(tag)
    session.flush()
    return tag


def require_valid_visibility(visibility: str) -> str:
    normalized = str(visibility or "").strip() or TAG_VISIBILITY_PRIVATE
    if normalized not in VALID_TAG_VISIBILITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported tag visibility: {normalized}",
        )
    return normalized


def get_tag_by_canonical_id(session: Session, tag_id: str) -> TagRegistry | None:
    normalized = str(tag_id or "").strip()
    if not normalized:
        return None
    if not hasattr(session, "get"):
        return None
    return session.get(TagRegistry, normalized)


def get_tag_by_any_ref(session: Session, tag_ref: str) -> TagRegistry | None:
    normalized = str(tag_ref or "").strip()
    if not normalized:
        return None
    if not hasattr(session, "get"):
        return TagRegistry(
            id=normalized,
            tag_id=normalized,
            brief="",
            visibility=TAG_VISIBILITY_PRIVATE,
            is_isolated=False,
            is_system=False,
            meta_json={},
        )
    tag = session.get(TagRegistry, normalized)
    if tag:
        return tag
    return session.scalar(select(TagRegistry).where(TagRegistry.tag_id == normalized))


def require_canonical_tag(session: Session, tag_id: str) -> TagRegistry:
    if not hasattr(session, "get"):
        return TagRegistry(
            id=str(tag_id),
            tag_id=str(tag_id),
            brief="",
            visibility=TAG_VISIBILITY_PRIVATE,
            is_isolated=False,
            is_system=False,
            meta_json={},
        )
    tag = get_tag_by_canonical_id(session, tag_id)
    if tag:
        return tag
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")


def canonicalize_tag_refs(session: Session, refs: Iterable[str] | None, *, include_default: bool = False) -> list[str]:
    if not hasattr(session, "get"):
        resolved = sorted({str(raw) for raw in refs or [] if str(raw).strip()})
        return resolved
    resolved: list[str] = []
    for raw in refs or []:
        tag = get_tag_by_any_ref(session, str(raw))
        if not tag:
            continue
        if tag.id not in resolved:
            resolved.append(tag.id)
    if include_default:
        default_tag = ensure_default_tag(session)
        if default_tag.id not in resolved:
            resolved.insert(0, default_tag.id)
    return resolved


def ensure_target_default_binding(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> str:
    if not hasattr(session, "get"):
        return DEFAULT_TAG_SLUG
    default_tag = ensure_default_tag(session)
    if cocoon_id:
        binding = session.scalar(
            select(CocoonTagBinding).where(
                CocoonTagBinding.cocoon_id == cocoon_id,
                CocoonTagBinding.tag_id == default_tag.id,
            )
        )
        if not binding:
            session.add(CocoonTagBinding(cocoon_id=cocoon_id, tag_id=default_tag.id))
    if chat_group_id:
        binding = session.scalar(
            select(ChatGroupTagBinding).where(
                ChatGroupTagBinding.chat_group_id == chat_group_id,
                ChatGroupTagBinding.tag_id == default_tag.id,
            )
        )
        if not binding:
            session.add(ChatGroupTagBinding(chat_group_id=chat_group_id, tag_id=default_tag.id))
    session.flush()
    return default_tag.id


def ensure_state_default_tag(
    session: Session,
    state: SessionState,
) -> SessionState:
    if not hasattr(session, "get"):
        return state
    default_tag_id = ensure_default_tag(session).id
    active_tags = canonicalize_tag_refs(session, state.active_tags_json, include_default=True)
    if not active_tags:
        active_tags = [default_tag_id]
    if state.active_tags_json != active_tags:
        state.active_tags_json = active_tags
        session.flush()
    return state


def list_target_bound_tag_ids(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> list[str]:
    ensure_target_default_binding(session, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    if cocoon_id:
        return list(
            session.scalars(
                select(CocoonTagBinding.tag_id)
                .where(CocoonTagBinding.cocoon_id == cocoon_id)
                .order_by(CocoonTagBinding.created_at.asc())
            ).all()
        )
    if chat_group_id:
        return list(
            session.scalars(
                select(ChatGroupTagBinding.tag_id)
                .where(ChatGroupTagBinding.chat_group_id == chat_group_id)
                .order_by(ChatGroupTagBinding.created_at.asc())
            ).all()
        )
    return []


def is_tag_visible_in_target(
    session: Session,
    tag: TagRegistry,
    *,
    target_type: str,
    target_id: str,
) -> bool:
    if target_type == "cocoon":
        return True
    if is_system_tag(tag):
        return True
    visibility = require_valid_visibility(tag.visibility)
    if visibility == TAG_VISIBILITY_PUBLIC:
        return True
    if visibility == TAG_VISIBILITY_PRIVATE:
        return False
    return session.scalar(
        select(TagChatGroupVisibility).where(
            TagChatGroupVisibility.tag_id == tag.id,
            TagChatGroupVisibility.chat_group_id == target_id,
            TagChatGroupVisibility.is_visible.is_(True),
        )
    ) is not None


def list_visible_bound_tags(
    session: Session,
    *,
    target_type: str,
    target_id: str,
    include_system: bool = True,
) -> list[TagRegistry]:
    bound_tag_ids = list_target_bound_tag_ids(
        session,
        cocoon_id=target_id if target_type == "cocoon" else None,
        chat_group_id=target_id if target_type == "chat_group" else None,
    )
    if not bound_tag_ids:
        return []
    tags = list(
        session.scalars(select(TagRegistry).where(TagRegistry.id.in_(bound_tag_ids))).all()
    )
    ordered = sorted(tags, key=lambda item: (item.tag_id or "", item.id))
    visible: list[TagRegistry] = []
    for tag in ordered:
        if not include_system and is_system_tag(tag):
            continue
        if is_tag_visible_in_target(session, tag, target_type=target_type, target_id=target_id):
            visible.append(tag)
    return visible


def serialize_prompt_tag_catalog(
    session: Session,
    *,
    target_type: str,
    target_id: str,
) -> tuple[list[dict[str, str | int]], dict[int, dict[str, str]]]:
    visible_tags = list_visible_bound_tags(
        session,
        target_type=target_type,
        target_id=target_id,
        include_system=False,
    )
    catalog: list[dict[str, str | int]] = []
    by_index: dict[int, dict[str, str]] = {}
    for index, tag in enumerate(visible_tags, start=1):
        item = {
            "index": index,
            "id": tag.id,
            "tag_id": tag.tag_id,
            "brief": tag.brief,
        }
        catalog.append(item)
        by_index[index] = {"id": tag.id, "tag_id": tag.tag_id}
    return catalog, by_index


def replace_tag_visibility_groups(
    session: Session,
    tag: TagRegistry,
    chat_group_ids: Iterable[str],
) -> list[str]:
    normalized_ids = sorted({str(item).strip() for item in chat_group_ids if str(item).strip()})
    session.query(TagChatGroupVisibility).filter(TagChatGroupVisibility.tag_id == tag.id).delete(
        synchronize_session=False
    )
    for chat_group_id in normalized_ids:
        if session.get(ChatGroupRoom, chat_group_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat group not found: {chat_group_id}",
            )
        session.add(
            TagChatGroupVisibility(
                tag_id=tag.id,
                chat_group_id=chat_group_id,
                is_visible=True,
            )
        )
    session.flush()
    return normalized_ids


def list_visible_chat_group_ids(session: Session, tag_id: str) -> list[str]:
    return list(
        session.scalars(
            select(TagChatGroupVisibility.chat_group_id)
            .where(
                TagChatGroupVisibility.tag_id == tag_id,
                TagChatGroupVisibility.is_visible.is_(True),
            )
            .order_by(TagChatGroupVisibility.chat_group_id.asc())
        ).all()
    )


def reconcile_tag_storage(session: Session) -> None:
    default_tag_id = ensure_default_tag(session).id
    tag_by_ref = {
        **{tag.id: tag.id for tag in session.scalars(select(TagRegistry)).all()},
        **{tag.tag_id: tag.id for tag in session.scalars(select(TagRegistry)).all()},
    }

    def _normalize_list(values: Iterable[str] | None, *, include_default: bool = False) -> list[str]:
        normalized: list[str] = []
        for value in values or []:
            tag_id = tag_by_ref.get(str(value))
            if tag_id and tag_id not in normalized:
                normalized.append(tag_id)
        if include_default and default_tag_id not in normalized:
            normalized.insert(0, default_tag_id)
        return normalized

    for cocoon in session.scalars(select(Cocoon)).all():
        ensure_target_default_binding(session, cocoon_id=cocoon.id)
    for room in session.scalars(select(ChatGroupRoom)).all():
        ensure_target_default_binding(session, chat_group_id=room.id)

    for binding in session.scalars(select(CocoonTagBinding)).all():
        normalized = tag_by_ref.get(binding.tag_id)
        if normalized:
            binding.tag_id = normalized
    for binding in session.scalars(select(ChatGroupTagBinding)).all():
        normalized = tag_by_ref.get(binding.tag_id)
        if normalized:
            binding.tag_id = normalized
    for visibility in session.scalars(select(TagChatGroupVisibility)).all():
        normalized = tag_by_ref.get(visibility.tag_id)
        if normalized:
            visibility.tag_id = normalized
    for state in session.scalars(select(SessionState)).all():
        state.active_tags_json = _normalize_list(state.active_tags_json, include_default=True)
    for message in session.scalars(select(Message)).all():
        message.tags_json = _normalize_list(message.tags_json)
    for memory in session.scalars(select(MemoryChunk)).all():
        memory.tags_json = _normalize_list(memory.tags_json)
    for message_tag in session.scalars(select(MessageTag)).all():
        normalized = tag_by_ref.get(message_tag.tag_id)
        if normalized:
            message_tag.tag_id = normalized
    for memory_tag in session.scalars(select(MemoryTag)).all():
        normalized = tag_by_ref.get(memory_tag.tag_id)
        if normalized:
            memory_tag.tag_id = normalized
    session.flush()
