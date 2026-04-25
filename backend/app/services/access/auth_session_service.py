"""Authentication session orchestration service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuthSession, InviteCode, Role, User, UserGroupMember
from app.schemas.access.auth import RegisterRequest, TokenPair
from app.services.access.group_service import GroupService
from app.services.catalog.tag_policy import ensure_user_system_tag
from app.services.catalog.system_settings_service import SystemSettingsService
from app.services.security.encryption import hash_secret, verify_secret
from app.services.security.token_service import TokenService


class AuthSessionService:
    """Handles login, refresh, and logout flows around auth sessions."""

    def __init__(
        self,
        token_service: TokenService,
        settings: Settings,
        system_settings_service: SystemSettingsService | None = None,
        group_service: GroupService | None = None,
    ) -> None:
        self.token_service = token_service
        self.settings = settings
        self.system_settings_service = system_settings_service
        self.group_service = group_service or GroupService()

    def login(self, session: Session, username: str, password: str) -> TokenPair:
        """Validate credentials and issue a fresh token pair."""
        user = session.scalar(select(User).where(User.username == username))
        if not user or not verify_secret(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

        return self._issue_token_pair(session, user.id)

    def register(self, session: Session, payload: RegisterRequest) -> TokenPair:
        """Create a new user from a valid invite code when self-registration is enabled."""
        if not self.system_settings_service:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Registration is unavailable")

        current_settings = self.system_settings_service.get_settings(session)
        if not current_settings.allow_registration:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled")

        existing_user = session.scalar(select(User).where(User.username == payload.username))
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
        if payload.email:
            existing_email = session.scalar(select(User).where(User.email == payload.email))
            if existing_email:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

        invite_code = session.scalar(select(InviteCode).where(InviteCode.code == payload.invite_code))
        if not invite_code:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
        if invite_code.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite revoked")
        if invite_code.expires_at and invite_code.expires_at < datetime.now(UTC).replace(tzinfo=None):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite expired")
        if invite_code.quota_used >= invite_code.quota_total:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite quota exceeded")

        user_role = session.scalar(select(Role).where(Role.name == "user"))
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default user role is not configured",
            )

        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_secret(payload.password),
            role_id=user_role.id,
            is_active=True,
        )
        session.add(user)
        session.flush()
        ensure_user_system_tag(session, user.id)
        registration_group = self.group_service.resolve_registration_group(session, invite_code.registration_group_id)
        existing_membership = session.scalar(
            select(UserGroupMember).where(
                UserGroupMember.group_id == registration_group.id,
                UserGroupMember.user_id == user.id,
            )
        )
        if not existing_membership:
            session.add(UserGroupMember(group_id=registration_group.id, user_id=user.id, member_role="member"))
        invite_code.quota_used += 1
        session.flush()
        return self._issue_token_pair(session, user.id)

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

    def _issue_token_pair(self, session: Session, user_id: str) -> TokenPair:
        access_token = self.token_service.create_access_token(user_id)
        refresh_token = self.token_service.create_refresh_token(user_id)
        session.add(
            AuthSession(
                user_id=user_id,
                refresh_token_hash=hash_secret(refresh_token),
                expires_at=(
                    datetime.now(UTC).replace(tzinfo=None)
                    + timedelta(minutes=self.settings.refresh_token_expire_minutes)
                ),
            )
        )
        session.flush()
        return TokenPair(access_token=access_token, refresh_token=refresh_token)
