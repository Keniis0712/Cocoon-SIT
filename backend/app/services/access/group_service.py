"""User-group administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserGroup, UserGroupMember
from app.schemas.access.groups import GroupCreate, GroupMemberCreate, GroupUpdate


class GroupService:
    """Creates groups and manages group membership."""

    def list_groups(self, session: Session) -> list[UserGroup]:
        """Return groups ordered by newest first."""
        return list(session.scalars(select(UserGroup).order_by(UserGroup.created_at.desc())).all())

    def create_group(self, session: Session, payload: GroupCreate, user: User | None = None) -> UserGroup:
        """Create a user group."""
        group = UserGroup(name=payload.name, owner_user_id=user.id if user else None)
        session.add(group)
        session.flush()
        return group

    def update_group(self, session: Session, group_id: str, payload: GroupUpdate) -> UserGroup:
        """Update a group's mutable fields."""
        group = session.get(UserGroup, group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        if payload.name is not None:
            group.name = payload.name
        session.flush()
        return group

    def delete_group(self, session: Session, group_id: str) -> UserGroup:
        """Delete a group and its membership rows."""
        group = session.get(UserGroup, group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        session.query(UserGroupMember).filter(UserGroupMember.group_id == group_id).delete()
        session.delete(group)
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
        existing = session.scalar(
            select(UserGroupMember).where(
                UserGroupMember.group_id == group_id,
                UserGroupMember.user_id == payload.user_id,
            )
        )
        if existing:
            return existing
        member = UserGroupMember(group_id=group_id, user_id=payload.user_id, member_role=payload.member_role)
        session.add(member)
        session.flush()
        return member

    def remove_group_member(self, session: Session, group_id: str, user_id: str) -> UserGroupMember:
        """Remove a member from a group."""
        member = session.scalar(
            select(UserGroupMember).where(
                UserGroupMember.group_id == group_id,
                UserGroupMember.user_id == user_id,
            )
        )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group member not found")
        session.delete(member)
        session.flush()
        return member
