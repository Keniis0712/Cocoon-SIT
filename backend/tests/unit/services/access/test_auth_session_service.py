from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import Settings
from app.models import AuthSession, InviteCode, Role, User
from app.schemas.access.auth import RegisterRequest
from app.services.access.auth_session_service import AuthSessionService
from app.services.security.encryption import hash_secret
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


class _TokenService:
    def __init__(self):
        self.refresh_counter = 0
        self.decoded_tokens = {}

    def create_access_token(self, user_id: str) -> str:
        return f"access-{user_id}"

    def create_refresh_token(self, user_id: str) -> str:
        self.refresh_counter += 1
        token = f"refresh-{user_id}-{self.refresh_counter}"
        self.decoded_tokens[token] = {"typ": "refresh", "sub": user_id}
        return token

    def decode_token(self, token: str) -> dict:
        return self.decoded_tokens[token]


def test_auth_session_service_login_refresh_and_logout_persist_session_state():
    session_factory = _session_factory()
    token_service = _TokenService()
    service = AuthSessionService(token_service, Settings())

    with session_factory() as session:
        user = User(username="active-user", password_hash=hash_secret("secret"), is_active=True)
        session.add(user)
        session.commit()
        user_id = user.id

    with session_factory() as session:
        tokens = service.login(session, "active-user", "secret")
        persisted = session.scalar(select(AuthSession).where(AuthSession.user_id == user_id))
        assert persisted is not None
        assert persisted.refresh_token_hash != tokens.refresh_token
        assert persisted.revoked_at is None

        rotated = service.refresh(session, tokens.refresh_token)
        assert rotated.access_token == f"access-{user_id}"
        assert rotated.refresh_token != tokens.refresh_token
        assert persisted.refresh_token_hash != hash_secret(tokens.refresh_token)

        result = service.logout(session, rotated.refresh_token)
        assert result == {"message": "logged out"}
        assert persisted.revoked_at is not None

        assert service.logout(session, "missing-refresh-token") == {"message": "logged out"}


def test_auth_session_service_login_and_refresh_reject_invalid_inputs():
    session_factory = _session_factory()
    token_service = _TokenService()
    token_service.decoded_tokens["access-like-token"] = {"typ": "access", "sub": "user-1"}
    service = AuthSessionService(token_service, Settings())

    with session_factory() as session:
        session.add(User(username="inactive-user", password_hash=hash_secret("secret"), is_active=False))
        session.commit()

        with pytest.raises(HTTPException) as invalid_credentials:
            service.login(session, "inactive-user", "wrong")
        assert invalid_credentials.value.status_code == 401

        with pytest.raises(HTTPException) as inactive_user:
            service.login(session, "inactive-user", "secret")
        assert inactive_user.value.status_code == 403

        with pytest.raises(HTTPException) as invalid_type:
            service.refresh(session, "access-like-token")
        assert invalid_type.value.status_code == 401

        token_service.decoded_tokens["refresh-missing"] = {"typ": "refresh", "sub": "user-1"}
        with pytest.raises(HTTPException) as unknown_refresh:
            service.refresh(session, "refresh-missing")
        assert unknown_refresh.value.status_code == 401


def test_auth_session_service_register_validates_configuration_and_invite_state():
    session_factory = _session_factory()
    token_service = _TokenService()
    payload = RegisterRequest(
        username="fresh-user",
        password="secret123",
        email="fresh@example.com",
        invite_code="INVITE1",
    )

    with session_factory() as session:
        session.add(User(username="fresh-user", password_hash=hash_secret("secret"), is_active=True))
        session.commit()

        service = AuthSessionService(token_service, Settings())
        with pytest.raises(HTTPException) as unavailable:
            service.register(session, payload)
        assert unavailable.value.status_code == 503

    with session_factory() as session:
        session.add(User(username="admin", email="fresh@example.com", password_hash=hash_secret("secret"), is_active=True))
        session.commit()

        disabled = AuthSessionService(
            token_service,
            Settings(),
            system_settings_service=SimpleNamespace(get_settings=lambda _: SimpleNamespace(allow_registration=False)),
        )
        with pytest.raises(HTTPException) as registration_disabled:
            disabled.register(session, payload)
        assert registration_disabled.value.status_code == 403

        enabled = AuthSessionService(
            token_service,
            Settings(),
            system_settings_service=SimpleNamespace(get_settings=lambda _: SimpleNamespace(allow_registration=True)),
        )
        with pytest.raises(HTTPException) as duplicate_username:
            enabled.register(session, RegisterRequest(username="fresh-user", password="secret123", invite_code="MISS1"))
        assert duplicate_username.value.status_code == 400

        with pytest.raises(HTTPException) as duplicate_email:
            enabled.register(
                session,
                RegisterRequest(username="another-user", password="secret123", email="fresh@example.com", invite_code="MISS2"),
            )
        assert duplicate_email.value.status_code == 400

        with pytest.raises(HTTPException) as invite_missing:
            enabled.register(
                session,
                RegisterRequest(username="another-user", password="secret123", email="another@example.com", invite_code="MISS3"),
            )
        assert invite_missing.value.status_code == 404

        session.add(
            InviteCode(code="REVOKED", quota_total=1, revoked_at=datetime.now(UTC).replace(tzinfo=None))
        )
        session.add(
            InviteCode(
                code="EXPIRED",
                quota_total=1,
                expires_at=(datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None),
            )
        )
        session.add(InviteCode(code="FULL", quota_total=1, quota_used=1))
        session.commit()

        with pytest.raises(HTTPException) as invite_revoked:
            enabled.register(
                session,
                RegisterRequest(username="revoked-user", password="secret123", email="revoked@example.com", invite_code="REVOKED"),
            )
        assert invite_revoked.value.status_code == 400

        with pytest.raises(HTTPException) as invite_expired:
            enabled.register(
                session,
                RegisterRequest(username="expired-user", password="secret123", email="expired@example.com", invite_code="EXPIRED"),
            )
        assert invite_expired.value.status_code == 400

        with pytest.raises(HTTPException) as invite_full:
            enabled.register(
                session,
                RegisterRequest(username="full-user", password="secret123", email="full@example.com", invite_code="FULL"),
            )
        assert invite_full.value.status_code == 400


def test_auth_session_service_register_success_requires_user_role_and_consumes_invite():
    session_factory = _session_factory()
    token_service = _TokenService()
    service = AuthSessionService(
        token_service,
        Settings(),
        system_settings_service=SimpleNamespace(get_settings=lambda _: SimpleNamespace(allow_registration=True)),
    )

    with session_factory() as session:
        session.add(InviteCode(code="ROLEMISS", quota_total=1))
        session.commit()

        with pytest.raises(HTTPException) as missing_role:
            service.register(
                session,
                RegisterRequest(username="role-missing", password="secret123", email="role@example.com", invite_code="ROLEMISS"),
            )
        assert missing_role.value.status_code == 500

        user_role = Role(name="user", permissions_json={})
        session.add(user_role)
        session.add(InviteCode(code="READY123", quota_total=2))
        session.commit()

        tokens = service.register(
            session,
            RegisterRequest(username="registered-user", password="secret123", email="registered@example.com", invite_code="READY123"),
        )
        created_user = session.scalar(select(User).where(User.username == "registered-user"))
        invite = session.scalar(select(InviteCode).where(InviteCode.code == "READY123"))
        auth_session = session.scalar(select(AuthSession).where(AuthSession.user_id == created_user.id))

        assert tokens.token_type == "bearer"
        assert created_user is not None
        assert created_user.role_id == user_role.id
        assert invite is not None
        assert invite.quota_used == 1
        assert auth_session is not None
