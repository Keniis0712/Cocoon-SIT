"""Authentication session orchestration service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuthSession, User
from app.schemas.access.auth import TokenPair
from app.services.security.encryption import hash_secret, verify_secret
from app.services.security.token_service import TokenService


class AuthSessionService:
    """Handles login, refresh, and logout flows around auth sessions."""

    def __init__(self, token_service: TokenService, settings: Settings) -> None:
        self.token_service = token_service
        self.settings = settings

    def login(self, session: Session, username: str, password: str) -> TokenPair:
        """Validate credentials and issue a fresh token pair."""
        user = session.scalar(select(User).where(User.username == username))
        if not user or not verify_secret(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        access_token = self.token_service.create_access_token(user.id)
        refresh_token = self.token_service.create_refresh_token(user.id)
        session.add(
            AuthSession(
                user_id=user.id,
                refresh_token_hash=hash_secret(refresh_token),
                expires_at=(
                    datetime.now(UTC).replace(tzinfo=None)
                    + timedelta(minutes=self.settings.refresh_token_expire_minutes)
                ),
            )
        )
        session.flush()
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    def refresh(self, session: Session, refresh_token: str) -> TokenPair:
        """Rotate a refresh token and issue a new access token."""
        decoded = self.token_service.decode_token(refresh_token)
        if decoded.get("typ") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        token_hash = hash_secret(refresh_token)
        auth_session = session.scalar(
            select(AuthSession).where(
                AuthSession.refresh_token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
            )
        )
        if not auth_session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown refresh token")
        access_token = self.token_service.create_access_token(auth_session.user_id)
        next_refresh_token = self.token_service.create_refresh_token(auth_session.user_id)
        auth_session.refresh_token_hash = hash_secret(next_refresh_token)
        session.flush()
        return TokenPair(access_token=access_token, refresh_token=next_refresh_token)

    def logout(self, session: Session, refresh_token: str) -> dict[str, str]:
        """Revoke the persisted auth session associated with a refresh token."""
        token_hash = hash_secret(refresh_token)
        auth_session = session.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
        if auth_session:
            auth_session.revoked_at = datetime.now(UTC).replace(tzinfo=None)
            session.flush()
        return {"message": "logged out"}
