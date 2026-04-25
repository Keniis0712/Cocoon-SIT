from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import User
from app.schemas.access.auth import UserCreate, UserUpdate
from app.services.access.user_service import UserService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def _service():
    return UserService(SimpleNamespace(default_admin_username="admin"))


def test_user_service_lists_creates_and_updates_users():
    session_factory = _session_factory()
    service = _service()

    with session_factory() as session:
        actor = User(username="actor", email="actor@example.com", password_hash="hash-actor", role_id="role-admin")
        session.add(User(username="z-last", email="z@example.com", password_hash="hash-z"))
        session.add(User(username="a-first", email="a@example.com", password_hash="hash-a"))
        session.add(actor)
        session.commit()

        created = service.create_user(
            session,
            UserCreate(
                username="created",
                email="created@example.com",
                password="secret123",
                role_id="role-1",
                permissions_json={"users:read": True},
                is_active=False,
            ),
        )
        original_hash = created.password_hash
        listed = service.list_users(session)
        updated = service.update_user(
            session,
            actor,
            created.id,
            UserUpdate(
                username="updated",
                email="updated@example.com",
                role_id="role-2",
                permissions_json={"users:write": True},
                is_active=True,
                password="new-secret",
            ),
        )

        assert created.password_hash != "secret123"
        assert [user.username for user in listed][:2] == ["z-last", "a-first"]
        assert updated.username == "updated"
        assert updated.email == "updated@example.com"
        assert updated.role_id == "role-2"
        assert updated.permissions_json == {"users:write": True}
        assert updated.is_active is True
        assert updated.password_hash != original_hash


def test_user_service_update_raises_when_user_missing():
    session_factory = _session_factory()
    service = _service()

    with session_factory() as session:
        actor = User(username="actor", email="actor@example.com", password_hash="hash-actor")
        session.add(actor)
        session.flush()
        with pytest.raises(HTTPException) as exc_info:
            service.update_user(session, actor, "missing", UserUpdate(username="nobody"))

    assert exc_info.value.status_code == 404


def test_user_service_blocks_self_role_change():
    session_factory = _session_factory()
    service = _service()

    with session_factory() as session:
        user = User(username="admin", email="admin@example.com", password_hash="hash-admin", role_id="role-admin", is_active=True)
        session.add(user)
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            service.update_user(session, user, user.id, UserUpdate(role_id="role-user"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Users cannot change their own role, permissions, or active status"


def test_user_service_blocks_self_permission_change():
    session_factory = _session_factory()
    service = _service()

    with session_factory() as session:
        user = User(
            username="admin",
            email="admin@example.com",
            password_hash="hash-admin",
            role_id="role-admin",
            permissions_json={"users:write": True},
            is_active=True,
        )
        session.add(user)
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            service.update_user(session, user, user.id, UserUpdate(permissions_json={"users:write": False}))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Users cannot change their own role, permissions, or active status"


def test_user_service_blocks_bootstrap_admin_role_change_by_other_user():
    session_factory = _session_factory()
    service = _service()

    with session_factory() as session:
        actor = User(username="operator", email="operator@example.com", password_hash="hash-operator", role_id="role-operator")
        bootstrap_admin = User(
            username="admin",
            email="admin@example.com",
            password_hash="hash-admin",
            role_id="role-admin",
            is_active=True,
        )
        session.add(actor)
        session.add(bootstrap_admin)
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            service.update_user(session, actor, bootstrap_admin.id, UserUpdate(is_active=False))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Bootstrap admin role, permissions, and active status are managed by configuration"
