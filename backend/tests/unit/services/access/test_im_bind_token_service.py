from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import User, UserImBindToken
from app.services.access.im_bind_token_service import ImBindTokenService
from app.services.security.encryption import hash_secret
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_im_bind_token_service_issues_single_active_token_per_user():
    session_factory = _session_factory()
    service = ImBindTokenService(ttl_seconds=60)

    with session_factory() as session:
        user = User(username="bind-user", password_hash=hash_secret("secret"), is_active=True)
        session.add(user)
        session.commit()

        first_token, first_row = service.issue_for_user(session, user)
        second_token, second_row = service.issue_for_user(session, user)
        tokens = list(session.scalars(select(UserImBindToken).where(UserImBindToken.user_id == user.id)).all())

        assert first_token != second_token
        assert first_row.revoked_at is not None
        assert second_row.revoked_at is None
        assert len(tokens) == 2


def test_im_bind_token_service_verifies_username_and_token():
    session_factory = _session_factory()
    service = ImBindTokenService(ttl_seconds=60)

    with session_factory() as session:
        user = User(username="bind-user", password_hash=hash_secret("secret"), is_active=True)
        session.add(user)
        session.commit()

        token, row = service.issue_for_user(session, user)
        resolved = service.verify_user_token(session, username="bind-user", token=token)

        assert resolved.id == user.id
        assert row.last_validated_at is not None

        with pytest.raises(ValueError):
            service.verify_user_token(session, username="bind-user", token="wrong-token")


def test_im_bind_token_service_rejects_expired_tokens():
    session_factory = _session_factory()
    service = ImBindTokenService(ttl_seconds=60)

    with session_factory() as session:
        user = User(username="bind-user", password_hash=hash_secret("secret"), is_active=True)
        session.add(user)
        session.commit()

        token, row = service.issue_for_user(session, user)
        row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        session.flush()

        with pytest.raises(ValueError):
            service.verify_user_token(session, username="bind-user", token=token)

        assert row.revoked_at is not None
