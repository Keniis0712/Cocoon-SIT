"""Character catalog administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Character, CharacterAcl, Cocoon, User
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
        self._sync_public_visibility_acl(session, character)
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
        self._sync_public_visibility_acl(session, character)
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
            subject_type=(payload.subject_type or "").strip().upper(),
            subject_id=payload.subject_id,
            can_read=payload.can_read,
            can_use=payload.can_use,
        )
        session.add(acl)
        session.flush()
        return acl

    def delete_character(self, session: Session, character_id: str) -> Character:
        """Delete a character when no cocoon still depends on it."""
        character = session.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
        linked_cocoon = session.scalar(select(Cocoon.id).where(Cocoon.character_id == character_id).limit(1))
        if linked_cocoon:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Character is still used by an existing cocoon",
            )
        session.query(CharacterAcl).filter(CharacterAcl.character_id == character_id).delete()
        session.delete(character)
        session.flush()
        return character

    def delete_acl(self, session: Session, character_id: str, acl_id: str) -> CharacterAcl:
        """Delete a single ACL row for a character."""
        acl = session.get(CharacterAcl, acl_id)
        if not acl or acl.character_id != character_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character ACL not found")
        session.delete(acl)
        session.flush()
        return acl

    def _sync_public_visibility_acl(self, session: Session, character: Character) -> None:
        visibility = str((character.settings_json or {}).get("visibility") or "private").strip().lower()
        existing_acl = session.scalar(
            select(CharacterAcl).where(
                CharacterAcl.character_id == character.id,
                CharacterAcl.subject_type == "AUTHENTICATED_ALL",
            )
        )
        if visibility == "public":
            if existing_acl:
                existing_acl.can_read = True
                existing_acl.can_use = False
            else:
                session.add(
                    CharacterAcl(
                        character_id=character.id,
                        subject_type="AUTHENTICATED_ALL",
                        subject_id="*",
                        can_read=True,
                        can_use=False,
                    )
                )
        elif existing_acl:
            session.delete(existing_acl)
