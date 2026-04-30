"""Helpers for conversation targets shared by cocoons and chat-group rooms."""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import Cocoon, SessionState, TargetTaskState
from app.models.workspace import DEFAULT_RELATION_SCORE
from app.services.catalog.tag_policy import ensure_state_bound_tags, ensure_target_default_binding


def resolve_target_type(*, cocoon_id: str | None = None, chat_group_id: str | None = None) -> tuple[str, str]:
    if cocoon_id and not chat_group_id:
        return "cocoon", cocoon_id
    if chat_group_id and not cocoon_id:
        return "chat_group", chat_group_id
    raise ValueError("Exactly one of cocoon_id or chat_group_id must be provided")


def target_channel_key(*, cocoon_id: str | None = None, chat_group_id: str | None = None) -> str:
    target_type, target_id = resolve_target_type(cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    return f"{target_type}:{target_id}"


def build_target_filter(model, *, cocoon_id: str | None = None, chat_group_id: str | None = None):
    target_type, target_id = resolve_target_type(cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    if target_type == "cocoon":
        return and_(model.cocoon_id == target_id, model.chat_group_id.is_(None))
    return and_(model.chat_group_id == target_id, model.cocoon_id.is_(None))


def list_cocoon_lineage(session: Session, cocoon_id: str) -> list[Cocoon]:
    lineage: list[Cocoon] = []
    seen_ids: set[str] = set()
    current_id: str | None = cocoon_id
    guard = 0

    while current_id and guard < 128:
        guard += 1
        if current_id in seen_ids:
            break
        cocoon = session.get(Cocoon, current_id)
        if not cocoon:
            break
        lineage.append(cocoon)
        seen_ids.add(cocoon.id)
        current_id = cocoon.parent_id

    lineage.reverse()
    return lineage


def list_cocoon_lineage_ids(session: Session, cocoon_id: str) -> list[str]:
    return [item.id for item in list_cocoon_lineage(session, cocoon_id)]


def get_session_state(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> SessionState | None:
    state = session.scalar(
        select(SessionState).where(
            build_target_filter(SessionState, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
        )
    )
    if state:
        ensure_state_bound_tags(session, state)
    return state


def ensure_session_state(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> SessionState:
    state = get_session_state(session, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    if state:
        return state
    ensure_target_default_binding(session, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    state = SessionState(
        cocoon_id=cocoon_id,
        chat_group_id=chat_group_id,
        relation_score=DEFAULT_RELATION_SCORE,
        persona_json={},
        active_tags_json=[],
    )
    session.add(state)
    session.flush()
    return ensure_state_bound_tags(session, state)


def get_target_task_state(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> TargetTaskState | None:
    return session.scalar(
        select(TargetTaskState).where(
            build_target_filter(TargetTaskState, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
        )
    )


def ensure_target_task_state(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> TargetTaskState:
    state = get_target_task_state(session, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    if state:
        return state
    state = TargetTaskState(
        cocoon_id=cocoon_id,
        chat_group_id=chat_group_id,
        status="active",
        meta_json={},
    )
    session.add(state)
    session.flush()
    return state
