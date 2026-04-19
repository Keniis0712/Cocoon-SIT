"""Object-level authorization helpers."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditRun,
    Character,
    CharacterAcl,
    ChatGroupMember,
    ChatGroupRoom,
    Cocoon,
    Role,
    User,
    UserGroupMember,
)


class AuthorizationService:
    """Applies object-level access rules for characters, cocoons, and derived resources."""

    def is_admin(self, session: Session, user: User) -> bool:
        if not user.role_id:
            return False
        role = session.get(Role, user.role_id)
        return bool(role and role.name == "admin")

    def _group_ids_for_user(self, session: Session, user_id: str) -> set[str]:
        return {
            item.group_id
            for item in session.scalars(
                select(UserGroupMember).where(UserGroupMember.user_id == user_id)
            ).all()
        }

    def can_read_character(self, session: Session, user: User, character: Character) -> bool:
        if self.is_admin(session, user):
            return True
        if character.created_by_user_id == user.id:
            return True
        group_ids = self._group_ids_for_user(session, user.id)
        for acl in session.scalars(
            select(CharacterAcl).where(CharacterAcl.character_id == character.id)
        ).all():
            if not acl.can_read:
                continue
            if acl.subject_type == "user" and acl.subject_id == user.id:
                return True
            if acl.subject_type == "role" and user.role_id and acl.subject_id == user.role_id:
                return True
            if acl.subject_type == "group" and acl.subject_id in group_ids:
                return True
        return False

    def can_use_character(self, session: Session, user: User, character: Character) -> bool:
        if self.is_admin(session, user):
            return True
        if character.created_by_user_id == user.id:
            return True
        group_ids = self._group_ids_for_user(session, user.id)
        for acl in session.scalars(
            select(CharacterAcl).where(CharacterAcl.character_id == character.id)
        ).all():
            if not acl.can_use:
                continue
            if acl.subject_type == "user" and acl.subject_id == user.id:
                return True
            if acl.subject_type == "role" and user.role_id and acl.subject_id == user.role_id:
                return True
            if acl.subject_type == "group" and acl.subject_id in group_ids:
                return True
        return False

    def require_character_read(self, session: Session, user: User, character_id: str) -> Character:
        character = session.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
        if not self.can_read_character(session, user, character):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Character access denied")
        return character

    def require_character_use(self, session: Session, user: User, character_id: str) -> Character:
        character = session.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
        if not self.can_use_character(session, user, character):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Character access denied")
        return character

    def filter_visible_characters(self, session: Session, user: User, characters: list[Character]) -> list[Character]:
        return [item for item in characters if self.can_read_character(session, user, item)]

    def can_access_cocoon(self, session: Session, user: User, cocoon: Cocoon, *, write: bool) -> bool:
        if self.is_admin(session, user):
            return True
        if cocoon.owner_user_id == user.id:
            return True
        character = session.get(Character, cocoon.character_id)
        if not character:
            return False
        if write:
            return self.can_use_character(session, user, character)
        return self.can_read_character(session, user, character)

    def require_cocoon_access(self, session: Session, user: User, cocoon_id: str, *, write: bool) -> Cocoon:
        cocoon = session.get(Cocoon, cocoon_id)
        if not cocoon:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cocoon not found")
        if not self.can_access_cocoon(session, user, cocoon, write=write):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cocoon access denied")
        return cocoon

    def filter_visible_cocoons(self, session: Session, user: User, cocoons: list[Cocoon], *, write: bool = False) -> list[Cocoon]:
        return [item for item in cocoons if self.can_access_cocoon(session, user, item, write=write)]

    def require_pull_merge_access(
        self,
        session: Session,
        user: User,
        *,
        source_cocoon_id: str,
        target_cocoon_id: str,
    ) -> tuple[Cocoon, Cocoon]:
        source = self.require_cocoon_access(session, user, source_cocoon_id, write=False)
        target = self.require_cocoon_access(session, user, target_cocoon_id, write=True)
        return source, target

    def get_chat_group_membership(
        self,
        session: Session,
        user_id: str,
        room_id: str,
    ) -> ChatGroupMember | None:
        return session.scalar(
            select(ChatGroupMember).where(
                ChatGroupMember.room_id == room_id,
                ChatGroupMember.user_id == user_id,
            )
        )

    def can_read_chat_group(self, session: Session, user: User, room: ChatGroupRoom) -> bool:
        if self.is_admin(session, user):
            return True
        if room.owner_user_id == user.id:
            return True
        return self.get_chat_group_membership(session, user.id, room.id) is not None

    def can_chat_in_chat_group(self, session: Session, user: User, room: ChatGroupRoom) -> bool:
        return self.can_read_chat_group(session, user, room)

    def can_manage_chat_group(self, session: Session, user: User, room: ChatGroupRoom) -> bool:
        if self.is_admin(session, user):
            return True
        if room.owner_user_id == user.id:
            return True
        membership = self.get_chat_group_membership(session, user.id, room.id)
        return bool(membership and membership.member_role == "admin")

    def require_chat_group_access(
        self,
        session: Session,
        user: User,
        room_id: str,
        *,
        write: bool = False,
        manage: bool = False,
        owner: bool = False,
    ) -> ChatGroupRoom:
        room = session.get(ChatGroupRoom, room_id)
        if not room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat group room not found")
        if owner:
            if self.is_admin(session, user) or room.owner_user_id == user.id:
                return room
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chat group owner access denied")
        if manage:
            if self.can_manage_chat_group(session, user, room):
                return room
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chat group management denied")
        if write:
            if self.can_chat_in_chat_group(session, user, room):
                return room
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chat group chat access denied")
        if self.can_read_chat_group(session, user, room):
            return room
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chat group access denied")

    def filter_visible_chat_groups(
        self,
        session: Session,
        user: User,
        rooms: list[ChatGroupRoom],
    ) -> list[ChatGroupRoom]:
        return [item for item in rooms if self.can_read_chat_group(session, user, item)]

    def can_view_audit_run(self, session: Session, user: User, run: AuditRun) -> bool:
        if run.cocoon_id is not None:
            cocoon = session.get(Cocoon, run.cocoon_id)
            return bool(cocoon and self.can_access_cocoon(session, user, cocoon, write=False))
        if run.chat_group_id is not None:
            room = session.get(ChatGroupRoom, run.chat_group_id)
            return bool(room and self.can_read_chat_group(session, user, room))
        return self.is_admin(session, user)

    def filter_visible_audit_runs(self, session: Session, user: User, runs: list[AuditRun]) -> list[AuditRun]:
        return [item for item in runs if self.can_view_audit_run(session, user, item)]
