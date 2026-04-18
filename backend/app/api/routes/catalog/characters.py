from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import Character, CharacterAcl, User
from app.schemas.catalog.characters import (
    CharacterAclCreate,
    CharacterAclOut,
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
)


router = APIRouter()


@router.get("", response_model=list[CharacterOut])
def list_characters(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("characters:read")),
) -> list[Character]:
    items = db.info["container"].character_service.list_characters(db)
    return db.info["container"].authorization_service.filter_visible_characters(db, user, items)


@router.post("", response_model=CharacterOut)
def create_character(
    payload: CharacterCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("characters:write")),
) -> Character:
    return db.info["container"].character_service.create_character(db, payload, user)


@router.patch("/{character_id}", response_model=CharacterOut)
def update_character(
    character_id: str,
    payload: CharacterUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("characters:write")),
) -> Character:
    db.info["container"].authorization_service.require_character_use(db, user, character_id)
    return db.info["container"].character_service.update_character(db, character_id, payload)


@router.get("/{character_id}/acl", response_model=list[CharacterAclOut])
def list_character_acl(
    character_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("characters:read")),
) -> list[CharacterAcl]:
    db.info["container"].authorization_service.require_character_read(db, user, character_id)
    return db.info["container"].character_service.list_acl(db, character_id)


@router.post("/{character_id}/acl", response_model=CharacterAclOut)
def create_character_acl(
    character_id: str,
    payload: CharacterAclCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("characters:write")),
) -> CharacterAcl:
    db.info["container"].authorization_service.require_character_use(db, user, character_id)
    return db.info["container"].character_service.create_acl(db, character_id, payload)
