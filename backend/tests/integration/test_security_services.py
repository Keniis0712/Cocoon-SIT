import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import User

pytestmark = pytest.mark.integration


def test_token_service_round_trip_and_active_user_resolution(client):
    container = client.app.state.container
    with container.session_factory() as session:
        user = session.scalars(select(User).where(User.username == "admin")).first()
        token = container.token_service.create_access_token(user.id)
        resolved = container.token_authentication_service.resolve_active_user(session, token)
        assert resolved.id == user.id


def test_token_authentication_service_rejects_invalid_token(client):
    container = client.app.state.container
    with container.session_factory() as session:
        with pytest.raises(HTTPException):
            container.token_authentication_service.resolve_active_user(session, "not-a-token")
