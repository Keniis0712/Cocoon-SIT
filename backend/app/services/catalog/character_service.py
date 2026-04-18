"""Character catalog administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Character, CharacterAcl, User
from app.schemas.catalog.characters import CharacterAclCreate, CharacterCreate, CharacterUpdate


class CharacterService:
    """Creates, lists, and updates characters plus their ACL entries."""

    def list_characters(self, session: Session) -> list[Character]:
        """Return characters ordered by creation time."""
        return list(session.scalars(select(Character).order_by(Character.created_at.asc())).all())

    def create_character(self, session: Session, payload: CharacterCreate, user: User) -> Character:
        """Create a character attributed to the acting user."""
        character = Character(
            name=payload.name,
            prompt_summary=payload.prompt_summary,
            settings_json=payload.settings_json,
            created_by_user_id=user.id,
        )
        session.add(character)
        session.flush()
        return character

    def update_character(self, session: Session, character_id: str, payload: CharacterUpdate) -> Character:
        """Patch a character."""
        character = session.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
        if payload.name is not None:
            character.name = payload.name
        if payload.prompt_summary is not None:
            character.prompt_summary = payload.prompt_summary
        if payload.settings_json is not None:
            character.settings_json = payload.settings_json
        session.flush()
        return character

    def list_acl(self, session: Session, character_id: str) -> list[CharacterAcl]:
        """Return ACL rows for a character."""
        return list(
            session.scalars(
                select(CharacterAcl)
                .where(CharacterAcl.character_id == character_id)
                .order_by(CharacterAcl.created_at.asc())
            ).all()
        )

    def create_acl(self, session: Session, character_id: str, payload: CharacterAclCreate) -> CharacterAcl:
        """Create an ACL row for a character."""
        character = session.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
        acl = CharacterAcl(
            character_id=character_id,
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            can_read=payload.can_read,
            can_use=payload.can_use,
        )
        session.add(acl)
        session.flush()
        return acl
