"""User-group administration service."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserGroup, UserGroupManagementGrant, UserGroupMember
from app.schemas.access.groups import GroupCreate, GroupManagementGrantCreate, GroupMemberCreate, GroupUpdate

ROOT_GROUP_ID = "root-group"
ROOT_GROUP_NAME = "Root Group"
ROOT_GROUP_DESCRIPTION = "Fallback group for new registrations and orphaned memberships."


@dataclass(slots=True)
class GroupView:
    id: str
    name: str
    owner_user_id: str | None
    parent_group_id: str | None
    group_path: str
    description: str | None
    created_at: object
    updated_at: object


class GroupService:
    """Creates groups and manages group membership."""

    def ensure_root_group(self, session: Session) -> UserGroup:
        """Create the root group on demand so registration can always fall back safely."""
        group = session.get(UserGroup, ROOT_GROUP_ID)
        if group:
            return group

        group = UserGroup(
            id=ROOT_GROUP_ID,
            name=ROOT_GROUP_NAME,
            owner_user_id=None,
            parent_group_id=None,
            description=ROOT_GROUP_DESCRIPTION,
        )
        session.add(group)
        session.flush()
        return group

    def list_groups(self, session: Session) -> list[UserGroup]:
        """Return groups ordered with the root group first."""
        self.ensure_root_group(session)
        groups = list(session.scalars(select(UserGroup)).all())
        groups.sort(key=lambda item: (0 if item.id == ROOT_GROUP_ID else 1, -item.created_at.timestamp()))
        return groups

    def list_descendant_group_ids(self, session: Session, root_group_ids: list[str] | set[str]) -> list[str]:
        roots = [group_id for group_id in root_group_ids if group_id]
        if not roots:
            return []
        children_by_parent: dict[str | None, list[str]] = {}
        for group in self.list_groups(session):
            children_by_parent.setdefault(group.parent_group_id, []).append(group.id)

        ordered: list[str] = []
        seen: set[str] = set()
        queue = list(roots)
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            ordered.append(current)
            queue.extend(children_by_parent.get(current, []))
        return ordered

    def list_ancestor_group_ids(self, session: Session, group_id: str | None) -> list[str]:
        if not group_id:
            return []
        ordered: list[str] = []
        current_group_id = group_id
        guard = 0
        while current_group_id and guard < 64:
            ordered.append(current_group_id)
            group = session.get(UserGroup, current_group_id)
            if not group:
                break
            current_group_id = group.parent_group_id
            guard += 1
        return ordered

    def create_group(self, session: Session, payload: GroupCreate, user: User | None = None) -> UserGroup:
        """Create a user group under the requested parent, defaulting to the root group."""
        root_group = self.ensure_root_group(session)
        parent_group_id = payload.parent_group_id or root_group.id
        if parent_group_id != root_group.id:
            self._require_group(session, parent_group_id)

        group = UserGroup(
            name=payload.name,
            owner_user_id=user.id if user else None,
            parent_group_id=parent_group_id,
            description=payload.description,
        )
        session.add(group)
        session.flush()
        return group

    def update_group(self, session: Session, group_id: str, payload: GroupUpdate) -> UserGroup:
        """Update a group's mutable fields."""
        group = self._require_group(session, group_id)
        root_group = self.ensure_root_group(session)

        if "name" in payload.model_fields_set and payload.name is not None:
            group.name = payload.name
        if "description" in payload.model_fields_set:
            group.description = payload.description
        if "parent_group_id" in payload.model_fields_set:
            next_parent_id = payload.parent_group_id or root_group.id
            if group.id == ROOT_GROUP_ID and next_parent_id is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Root group cannot have a parent")
            if next_parent_id == group.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group cannot be its own parent")
            parent = self._require_group(session, next_parent_id)
            self._ensure_no_cycle(session, group, parent.id)
            group.parent_group_id = parent.id

        session.flush()
        return group

    def delete_group(self, session: Session, group_id: str) -> UserGroup:
        """Delete a group, re-parenting child groups back to the root group."""
        group = self._require_group(session, group_id)
        if group.id == ROOT_GROUP_ID:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Root group cannot be deleted")

        root_group = self.ensure_root_group(session)
        for child in session.scalars(select(UserGroup).where(UserGroup.parent_group_id == group_id)).all():
            child.parent_group_id = root_group.id

        session.query(UserGroupMember).filter(UserGroupMember.group_id == group_id).delete()
        session.delete(group)
        session.flush()
        return group

    def list_group_members(self, session: Session, group_id: str) -> list[UserGroupMember]:
        """Return members of a group ordered by creation time."""
        self._require_group(session, group_id)
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
        self._require_group(session, group_id)
        if not session.get(User, payload.user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
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

    def resolve_registration_group(self, session: Session, requested_group_id: str | None) -> UserGroup:
        """Return the requested group when present, otherwise the guaranteed root group."""
        root_group = self.ensure_root_group(session)
        if not requested_group_id:
            return root_group
        group = session.get(UserGroup, requested_group_id)
        return group or root_group

    def list_management_grants(self, session: Session) -> list[UserGroupManagementGrant]:
        return list(
            session.scalars(
                select(UserGroupManagementGrant).order_by(UserGroupManagementGrant.created_at.asc())
            ).all()
        )

    def create_management_grant(
        self,
        session: Session,
        payload: GroupManagementGrantCreate,
    ) -> UserGroupManagementGrant:
        if not session.get(User, payload.user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._require_group(session, payload.group_id)
        existing = session.scalar(
            select(UserGroupManagementGrant).where(
                UserGroupManagementGrant.user_id == payload.user_id,
                UserGroupManagementGrant.group_id == payload.group_id,
            )
        )
        if existing:
            return existing
        grant = UserGroupManagementGrant(user_id=payload.user_id, group_id=payload.group_id)
        session.add(grant)
        session.flush()
        return grant

    def delete_management_grant(self, session: Session, grant_id: str) -> UserGroupManagementGrant:
        grant = session.get(UserGroupManagementGrant, grant_id)
        if not grant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Management grant not found")
        session.delete(grant)
        session.flush()
        return grant

    def management_grant_group_ids_for_user(self, session: Session, user_id: str) -> list[str]:
        return list(
            session.scalars(
                select(UserGroupManagementGrant.group_id).where(UserGroupManagementGrant.user_id == user_id)
            ).all()
        )

    def build_group_view(self, session: Session, group: UserGroup) -> GroupView:
        """Serialize a group together with a human-readable path."""
        return GroupView(
            id=group.id,
            name=group.name,
            owner_user_id=group.owner_user_id,
            parent_group_id=group.parent_group_id,
            group_path=self._group_path(session, group),
            description=group.description,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    def group_path_by_id(self, session: Session, group_id: str | None) -> str | None:
        if not group_id:
            return None
        group = session.get(UserGroup, group_id)
        if not group:
            return None
        return self._group_path(session, group)

    def _require_group(self, session: Session, group_id: str) -> UserGroup:
        group = session.get(UserGroup, group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        return group

    def _group_path(self, session: Session, group: UserGroup) -> str:
        parts = [group.name]
        current_parent_id = group.parent_group_id
        guard = 0
        while current_parent_id and guard < 32:
            parent = session.get(UserGroup, current_parent_id)
            if not parent:
                break
            parts.append(parent.name)
            current_parent_id = parent.parent_group_id
            guard += 1
        return " / ".join(reversed(parts))

    def _ensure_no_cycle(self, session: Session, group: UserGroup, parent_group_id: str) -> None:
        current_parent_id = parent_group_id
        guard = 0
        while current_parent_id and guard < 64:
            if current_parent_id == group.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group parent would create a cycle")
            parent = session.get(UserGroup, current_parent_id)
            if not parent:
                return
            current_parent_id = parent.parent_group_id
            guard += 1
