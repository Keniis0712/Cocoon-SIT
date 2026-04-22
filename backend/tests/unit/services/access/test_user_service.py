import pytest
from fastapi import HTTPException

from app.models import User
from app.schemas.access.auth import UserCreate, UserUpdate
from app.services.access.user_service import UserService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_user_service_lists_creates_and_updates_users():
    session_factory = _session_factory()
    service = UserService()

    with session_factory() as session:
        session.add(User(username="z-last", email="z@example.com", password_hash="hash-z"))
        session.add(User(username="a-first", email="a@example.com", password_hash="hash-a"))
        session.commit()

        created = service.create_user(
            session,
            UserCreate(
                username="created",
                email="created@example.com",
                password="secret123",
                role_id="role-1",
                is_active=False,
            ),
        )
        original_hash = created.password_hash
        listed = service.list_users(session)
        updated = service.update_user(
            session,
            created.id,
            UserUpdate(
                username="updated",
                email="updated@example.com",
                role_id="role-2",
                is_active=True,
                password="new-secret",
            ),
        )

        assert created.password_hash != "secret123"
        assert [user.username for user in listed][:2] == ["z-last", "a-first"]
        assert updated.username == "updated"
        assert updated.email == "updated@example.com"
        assert updated.role_id == "role-2"
        assert updated.is_active is True
        assert updated.password_hash != original_hash


def test_user_service_update_raises_when_user_missing():
    session_factory = _session_factory()
    service = UserService()

    with session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            service.update_user(session, "missing", UserUpdate(username="nobody"))

    assert exc_info.value.status_code == 404
