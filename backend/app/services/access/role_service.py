"""Role administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role
from app.schemas.access.auth import RoleCreate, RoleUpdate


class RoleService:
    """Creates, lists, and updates roles."""

    def list_roles(self, session: Session) -> list[Role]:
        """Return roles ordered by creation time."""
        return list(session.scalars(select(Role).order_by(Role.created_at.asc())).all())

    def create_role(self, session: Session, payload: RoleCreate) -> Role:
        """Create a role record."""
        role = Role(name=payload.name, permissions_json=payload.permissions_json)
        session.add(role)
        session.flush()
        return role

    def update_role(self, session: Session, role_id: str, payload: RoleUpdate) -> Role:
        """Patch a role record."""
        role = session.get(Role, role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        if payload.name is not None:
            role.name = payload.name
        if payload.permissions_json is not None:
            role.permissions_json = payload.permissions_json
        session.flush()
        return role
