"""Helpers for conversation targets shared by cocoons and chat-group rooms."""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import SessionState
from app.models.workspace import DEFAULT_RELATION_SCORE
from app.services.catalog.tag_policy import ensure_state_default_tag, ensure_target_default_binding


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
        ensure_state_default_tag(session, state)
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
    return ensure_state_default_tag(session, state)
