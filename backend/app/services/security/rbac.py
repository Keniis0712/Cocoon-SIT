"""RBAC helpers for permission lookup and enforcement."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Role, User


def list_permissions_for_user(session: Session, user: User) -> set[str]:
    """Return the effective permission set for the provided user."""
    if not user.role_id:
        return set()
    role = session.get(Role, user.role_id)
    if not role:
        return set()
    return {name for name, allowed in role.permissions_json.items() if allowed}


def require_permission(session: Session, user: User, permission: str) -> None:
    """Raise 403 when the user lacks the requested permission."""
    permissions = list_permissions_for_user(session, user)
    if permission not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {permission}",
        )
