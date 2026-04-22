import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import AuthSession, User

pytestmark = pytest.mark.integration


def test_auth_session_service_login_refresh_and_logout(client):
    container = client.app.state.container
    with container.session_factory() as session:
        tokens = container.auth_session_service.login(session, "admin", "admin")
        session.commit()
        assert tokens.access_token
        assert tokens.refresh_token

    with container.session_factory() as session:
        rotated = container.auth_session_service.refresh(session, tokens.refresh_token)
        session.commit()
        assert rotated.access_token
        assert rotated.refresh_token != tokens.refresh_token

    with container.session_factory() as session:
        result = container.auth_session_service.logout(session, rotated.refresh_token)
        session.commit()
        auth_session = session.scalar(select(AuthSession).where(AuthSession.revoked_at.is_not(None)))
        assert result["message"] == "logged out"
        assert auth_session is not None


def test_auth_session_service_rejects_invalid_credentials(client):
    container = client.app.state.container
    with container.session_factory() as session:
        with pytest.raises(HTTPException):
            container.auth_session_service.login(session, "admin", "wrong-password")
