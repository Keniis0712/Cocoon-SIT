"""User administration service."""

from __future__ import annotations

from app.core.config import Settings
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.access.auth import UserCreate, UserUpdate
from app.services.catalog.tag_policy import ensure_user_system_tag
from app.services.security.encryption import hash_secret


class UserService:
    """Creates, lists, and updates users."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def list_users(self, session: Session) -> list[User]:
        """Return users ordered by creation time."""
        return list(session.scalars(select(User).order_by(User.created_at.asc())).all())

    def create_user(self, session: Session, payload: UserCreate) -> User:
        """Create a user with a hashed password."""
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_secret(payload.password),
            role_id=payload.role_id,
            permissions_json=payload.permissions_json,
            is_active=payload.is_active,
        )
        session.add(user)
        session.flush()
        ensure_user_system_tag(session, user.id)
        return user

    def update_user(self, session: Session, actor: User, user_id: str, payload: UserUpdate) -> User:
        """Patch an existing user."""
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._validate_update(actor, user, payload)
        if payload.username is not None:
            user.username = payload.username
        if payload.email is not None:
            user.email = payload.email
        if payload.role_id is not None:
            user.role_id = payload.role_id
        if payload.permissions_json is not None:
            user.permissions_json = payload.permissions_json
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.password is not None:
            user.password_hash = hash_secret(payload.password)
        session.flush()
        return user

    def _validate_update(self, actor: User, user: User, payload: UserUpdate) -> None:
        role_change = payload.role_id is not None and payload.role_id != user.role_id
        permission_change = (
            payload.permissions_json is not None
            and payload.permissions_json != (user.permissions_json or {})
        )
        active_change = payload.is_active is not None and payload.is_active != user.is_active

        if actor.id == user.id and (role_change or permission_change or active_change):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Users cannot change their own role, permissions, or active status",
            )
        if self._is_bootstrap_admin(user) and (role_change or permission_change or active_change):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bootstrap admin role, permissions, and active status are managed by configuration",
            )

    def _is_bootstrap_admin(self, user: User) -> bool:
        return user.username == self.settings.default_admin_username
