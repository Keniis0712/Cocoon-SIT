"""RBAC helpers for permission lookup and enforcement."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Role, User


def get_role_for_user(session: Session, user: User) -> Role | None:
    if not user.role_id:
        return None
    return session.get(Role, user.role_id)


def get_effective_permission_map(session: Session, user: User) -> dict[str, bool]:
    permissions: dict[str, bool] = {}
    role = get_role_for_user(session, user)
    if role:
        permissions.update({name: bool(allowed) for name, allowed in (role.permissions_json or {}).items()})
    for name, allowed in (getattr(user, "permissions_json", None) or {}).items():
        permissions[name] = bool(allowed)
    return permissions


def list_permissions_for_user(session: Session, user: User) -> set[str]:
    """Return the effective permission set for the provided user."""
    return {
        name
        for name, allowed in get_effective_permission_map(session, user).items()
        if allowed
    }


def require_permission(session: Session, user: User, permission: str) -> None:
    """Raise 403 when the user lacks the requested permission."""
    permissions = list_permissions_for_user(session, user)
    if permission not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {permission}",
        )
