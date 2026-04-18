from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import Cocoon, SessionState, User
from app.schemas.workspace.cocoons import (
    CocoonCreate,
    CocoonOut,
    CocoonTreeNode,
    CocoonUpdate,
    SessionStateOut,
)


router = APIRouter()


@router.get("", response_model=list[CocoonOut])
def list_cocoons(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[Cocoon]:
    items = list(db.scalars(select(Cocoon).order_by(Cocoon.created_at.asc())).all())
    return db.info["container"].authorization_service.filter_visible_cocoons(db, user, items)


@router.post("", response_model=CocoonOut)
def create_cocoon(
    payload: CocoonCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> Cocoon:
    cocoon = Cocoon(
        name=payload.name,
        character_id=payload.character_id,
        selected_model_id=payload.selected_model_id,
        parent_id=payload.parent_id,
        owner_user_id=user.id,
        default_temperature=payload.default_temperature,
        max_context_messages=payload.max_context_messages,
    )
    db.add(cocoon)
    db.flush()
    db.add(SessionState(cocoon_id=cocoon.id, persona_json={}, active_tags_json=[]))
    db.flush()
    return cocoon


@router.patch("/{cocoon_id}", response_model=CocoonOut)
def update_cocoon(
    cocoon_id: str,
    payload: CocoonUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> Cocoon:
    cocoon = db.info["container"].authorization_service.require_cocoon_access(
        db,
        user,
        cocoon_id,
        write=True,
    )
    for field in (
        "name",
        "character_id",
        "selected_model_id",
        "default_temperature",
        "max_context_messages",
        "auto_compaction_enabled",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(cocoon, field, value)
    db.flush()
    return cocoon


@router.get("/tree", response_model=list[CocoonTreeNode])
def cocoon_tree(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[CocoonTreeNode]:
    items = list(db.scalars(select(Cocoon).order_by(Cocoon.created_at.asc())).all())
    items = db.info["container"].authorization_service.filter_visible_cocoons(db, user, items)
    return db.info["container"].cocoon_tree_service.build_tree(items)


@router.get("/{cocoon_id}", response_model=CocoonOut)
def get_cocoon(
    cocoon_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> Cocoon:
    return db.info["container"].authorization_service.require_cocoon_access(
        db,
        user,
        cocoon_id,
        write=False,
    )


@router.get("/{cocoon_id}/state", response_model=SessionStateOut)
def get_session_state(
    cocoon_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> SessionState:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=False)
    state = db.get(SessionState, cocoon_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session state not found")
    return state
