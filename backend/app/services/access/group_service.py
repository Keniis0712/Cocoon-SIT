"""User-group administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserGroup, UserGroupMember
from app.schemas.access.groups import GroupCreate, GroupMemberCreate


class GroupService:
    """Creates groups and manages group membership."""

    def list_groups(self, session: Session) -> list[UserGroup]:
        """Return groups ordered by newest first."""
        return list(session.scalars(select(UserGroup).order_by(UserGroup.created_at.desc())).all())

    def create_group(self, session: Session, payload: GroupCreate) -> UserGroup:
        """Create a user group."""
        group = UserGroup(name=payload.name)
        session.add(group)
        session.flush()
        return group

    def list_group_members(self, session: Session, group_id: str) -> list[UserGroupMember]:
        """Return members of a group ordered by creation time."""
        return list(
            session.scalars(
                select(UserGroupMember)
                .where(UserGroupMember.group_id == group_id)
                .order_by(UserGroupMember.created_at.asc())
            ).all()
        )

    def add_group_member(
        self,
        session: Session,
        group_id: str,
        payload: GroupMemberCreate,
    ) -> UserGroupMember:
        """Add a member to a group."""
        group = session.get(UserGroup, group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        member = UserGroupMember(group_id=group_id, user_id=payload.user_id, member_role=payload.member_role)
        session.add(member)
        session.flush()
        return member
