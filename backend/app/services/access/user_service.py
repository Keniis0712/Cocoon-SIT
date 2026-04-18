"""User administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.access.auth import UserCreate, UserUpdate
from app.services.security.encryption import hash_secret


class UserService:
    """Creates, lists, and updates users."""

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
            is_active=payload.is_active,
        )
        session.add(user)
        session.flush()
        return user

    def update_user(self, session: Session, user_id: str, payload: UserUpdate) -> User:
        """Patch an existing user."""
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if payload.username is not None:
            user.username = payload.username
        if payload.email is not None:
            user.email = payload.email
        if payload.role_id is not None:
            user.role_id = payload.role_id
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.password is not None:
            user.password_hash = hash_secret(payload.password)
        session.flush()
        return user
