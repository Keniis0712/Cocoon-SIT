"""Shared tag helpers for user-owned private tags and target defaults."""

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
    User,
)

SYSTEM_TAG_SLUG = "default"
SYSTEM_TAG_BRIEF = "Default memory boundary automatically applied to every target."
TAG_VISIBILITY_PRIVATE = "private"
VALID_TAG_VISIBILITIES = {
    TAG_VISIBILITY_PRIVATE,
}


def is_system_tag(tag: TagRegistry | None) -> bool:
    if tag is None:
        return False
    return bool(tag.is_system)


def require_valid_visibility(visibility: str) -> str:
    normalized = str(visibility or "").strip() or TAG_VISIBILITY_PRIVATE
    if normalized not in VALID_TAG_VISIBILITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tags are private and cannot be shared or published",
        )
    return normalized


def ensure_user_system_tag(session: Session, user_id: str) -> TagRegistry:
    if not hasattr(session, "get"):
        return TagRegistry(
            id=SYSTEM_TAG_SLUG,
            owner_user_id=user_id,
            tag_id=SYSTEM_TAG_SLUG,
            brief=SYSTEM_TAG_BRIEF,
            visibility=TAG_VISIBILITY_PRIVATE,
            is_isolated=True,
            is_system=True,
            is_hidden=True,
            meta_json={"system": True},
        )

    tag = session.scalar(
        select(TagRegistry).where(
            TagRegistry.owner_user_id == user_id,
            TagRegistry.is_system.is_(True),
        )
    )
    if tag:
        tag.tag_id = SYSTEM_TAG_SLUG
        tag.brief = SYSTEM_TAG_BRIEF
        tag.visibility = TAG_VISIBILITY_PRIVATE
        tag.is_isolated = True
        tag.is_hidden = True
        tag.meta_json = {**(tag.meta_json or {}), "system": True}
        session.flush()
        return tag
    tag = TagRegistry(
        owner_user_id=user_id,
        tag_id=SYSTEM_TAG_SLUG,
        brief=SYSTEM_TAG_BRIEF,
        visibility=TAG_VISIBILITY_PRIVATE,
        is_isolated=True,
        is_system=True,
        is_hidden=True,
        meta_json={"system": True},
    )
    session.add(tag)
    session.flush()
    return tag


def ensure_all_users_system_tags(session: Session) -> None:
    for user_id in session.scalars(select(User.id)).all():
        ensure_user_system_tag(session, user_id)
    session.flush()


def list_tags_for_user(session: Session, user_id: str) -> list[TagRegistry]:
    return list(
        session.scalars(
            select(TagRegistry)
            .where(TagRegistry.owner_user_id == user_id)
            .order_by(TagRegistry.is_system.desc(), TagRegistry.tag_id.asc())
        ).all()
    )


def resolve_tag_owner_user_id_for_target(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> str | None:
    if not hasattr(session, "get"):
        return None
    if cocoon_id:
        cocoon = session.get(Cocoon, cocoon_id)
        return cocoon.owner_user_id if cocoon else None
    if chat_group_id:
        room = session.get(ChatGroupRoom, chat_group_id)
        return room.owner_user_id if room else None
    return None


def resolve_tag_owner_user_id_for_state(session: Session, state: SessionState) -> str | None:
    return resolve_tag_owner_user_id_for_target(
        session,
        cocoon_id=state.cocoon_id,
        chat_group_id=state.chat_group_id,
    )


def get_tag_by_canonical_id(
    session: Session,
    tag_id: str,
    *,
    owner_user_id: str | None = None,
) -> TagRegistry | None:
    normalized = str(tag_id or "").strip()
    if not normalized:
        return None
    if not hasattr(session, "get"):
        return None
    tag = session.get(TagRegistry, normalized)
    if tag and (owner_user_id is None or tag.owner_user_id == owner_user_id):
        return tag
    return None


def get_tag_by_any_ref(
    session: Session,
    tag_ref: str,
    *,
    owner_user_id: str | None = None,
) -> TagRegistry | None:
    normalized = str(tag_ref or "").strip()
    if not normalized:
        return None
    if not hasattr(session, "get"):
        return TagRegistry(
            id=normalized,
            owner_user_id=owner_user_id or "",
            tag_id=normalized,
            brief="",
            visibility=TAG_VISIBILITY_PRIVATE,
            is_isolated=True,
            is_system=False,
            is_hidden=False,
            meta_json={},
        )
    tag = get_tag_by_canonical_id(session, normalized, owner_user_id=owner_user_id)
    if tag:
        return tag
    if owner_user_id:
        return session.scalar(
            select(TagRegistry).where(
                TagRegistry.owner_user_id == owner_user_id,
                TagRegistry.tag_id == normalized,
            )
        )
    return None


def require_canonical_tag(
    session: Session,
    tag_id: str,
    *,
    owner_user_id: str | None = None,
) -> TagRegistry:
    tag = get_tag_by_any_ref(session, tag_id, owner_user_id=owner_user_id)
    if tag:
        return tag
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")


def canonicalize_tag_refs(
    session: Session,
    refs: Iterable[str] | None,
    *,
    include_default: bool = False,
    owner_user_id: str | None = None,
) -> list[str]:
    resolved: list[str] = []
    for raw in refs or []:
        tag = get_tag_by_any_ref(session, str(raw), owner_user_id=owner_user_id)
        if not tag:
            continue
        if owner_user_id and tag.owner_user_id != owner_user_id:
            continue
        if tag.id not in resolved:
            resolved.append(tag.id)
    if include_default and owner_user_id:
        default_tag = ensure_user_system_tag(session, owner_user_id)
        if default_tag.id not in resolved:
            resolved.insert(0, default_tag.id)
    return resolved


def ensure_target_default_binding(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> str:
    owner_user_id = resolve_tag_owner_user_id_for_target(
        session,
        cocoon_id=cocoon_id,
        chat_group_id=chat_group_id,
    )
    if not owner_user_id:
        return SYSTEM_TAG_SLUG
    default_tag = ensure_user_system_tag(session, owner_user_id)
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
    owner_user_id = resolve_tag_owner_user_id_for_state(session, state)
    active_tags = canonicalize_tag_refs(
        session,
        state.active_tags_json,
        include_default=True,
        owner_user_id=owner_user_id,
    )
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
    owner_user_id = resolve_tag_owner_user_id_for_target(
        session,
        cocoon_id=target_id if target_type == "cocoon" else None,
        chat_group_id=target_id if target_type == "chat_group" else None,
    )
    return bool(owner_user_id and tag.owner_user_id == owner_user_id)


def list_visible_bound_tags(
    session: Session,
    *,
    target_type: str,
    target_id: str,
    include_system: bool = True,
) -> list[TagRegistry]:
    owner_user_id = resolve_tag_owner_user_id_for_target(
        session,
        cocoon_id=target_id if target_type == "cocoon" else None,
        chat_group_id=target_id if target_type == "chat_group" else None,
    )
    if not owner_user_id:
        return []
    bound_tag_ids = list_target_bound_tag_ids(
        session,
        cocoon_id=target_id if target_type == "cocoon" else None,
        chat_group_id=target_id if target_type == "chat_group" else None,
    )
    if not bound_tag_ids:
        return []
    tags = list(
        session.scalars(
            select(TagRegistry).where(
                TagRegistry.id.in_(bound_tag_ids),
                TagRegistry.owner_user_id == owner_user_id,
            )
        ).all()
    )
    ordered = sorted(tags, key=lambda item: (item.is_system is False, item.tag_id or "", item.id))
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
        include_system=True,
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
    requested_ids = [str(item).strip() for item in chat_group_ids if str(item).strip()]
    if requested_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tags are private and cannot be shared with chat groups",
        )
    session.query(TagChatGroupVisibility).filter(TagChatGroupVisibility.tag_id == tag.id).delete(
        synchronize_session=False
    )
    session.flush()
    return []


def list_visible_chat_group_ids(session: Session, tag_id: str) -> list[str]:
    del session, tag_id
    return []


def reconcile_tag_storage(session: Session) -> None:
    ensure_all_users_system_tags(session)
    session.query(TagChatGroupVisibility).delete(synchronize_session=False)

    for cocoon in session.scalars(select(Cocoon)).all():
        ensure_target_default_binding(session, cocoon_id=cocoon.id)
    for room in session.scalars(select(ChatGroupRoom)).all():
        ensure_target_default_binding(session, chat_group_id=room.id)

    for state in session.scalars(select(SessionState)).all():
        owner_user_id = resolve_tag_owner_user_id_for_state(session, state)
        state.active_tags_json = canonicalize_tag_refs(
            session,
            state.active_tags_json,
            include_default=True,
            owner_user_id=owner_user_id,
        )
    for message in session.scalars(select(Message)).all():
        owner_user_id = resolve_tag_owner_user_id_for_target(
            session,
            cocoon_id=message.cocoon_id,
            chat_group_id=message.chat_group_id,
        )
        message.tags_json = canonicalize_tag_refs(
            session,
            message.tags_json,
            include_default=False,
            owner_user_id=owner_user_id,
        )
    for memory in session.scalars(select(MemoryChunk)).all():
        owner_user_id = memory.owner_user_id or resolve_tag_owner_user_id_for_target(
            session,
            cocoon_id=memory.cocoon_id,
            chat_group_id=memory.chat_group_id,
        )
        memory.tags_json = canonicalize_tag_refs(
            session,
            memory.tags_json,
            include_default=False,
            owner_user_id=owner_user_id,
        )
    for message_tag in session.scalars(select(MessageTag)).all():
        message = session.get(Message, message_tag.message_id)
        owner_user_id = resolve_tag_owner_user_id_for_target(
            session,
            cocoon_id=message.cocoon_id if message else None,
            chat_group_id=message.chat_group_id if message else None,
        )
        tag = get_tag_by_any_ref(session, message_tag.tag_id, owner_user_id=owner_user_id)
        if tag:
            message_tag.tag_id = tag.id
    for memory_tag in session.scalars(select(MemoryTag)).all():
        memory = session.get(MemoryChunk, memory_tag.memory_chunk_id)
        owner_user_id = (memory.owner_user_id if memory else None) or resolve_tag_owner_user_id_for_target(
            session,
            cocoon_id=memory.cocoon_id if memory else None,
            chat_group_id=memory.chat_group_id if memory else None,
        )
        tag = get_tag_by_any_ref(session, memory_tag.tag_id, owner_user_id=owner_user_id)
        if tag:
            memory_tag.tag_id = tag.id
    session.flush()
