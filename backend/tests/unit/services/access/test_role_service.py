import pytest
from fastapi import HTTPException

from app.schemas.access.auth import RoleCreate, RoleUpdate
from app.services.access.role_service import RoleService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_role_service_lists_creates_and_updates_roles():
    session_factory = _session_factory()
    service = RoleService()

    with session_factory() as session:
        first = service.create_role(
            session,
            RoleCreate(name="viewer", permissions_json={"workspace:read": True}),
        )
        second = service.create_role(
            session,
            RoleCreate(name="editor", permissions_json={"workspace:write": True}),
        )
        listed = service.list_roles(session)
        updated = service.update_role(
            session,
            first.id,
            RoleUpdate(name="viewer-updated", permissions_json={"workspace:read": False}),
        )

        assert [role.id for role in listed] == [first.id, second.id]
        assert updated.name == "viewer-updated"
        assert updated.permissions_json == {"workspace:read": False}


def test_role_service_update_raises_for_missing_role():
    session_factory = _session_factory()
    service = RoleService()

    with session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            service.update_role(session, "missing", RoleUpdate(name="nobody"))

    assert exc_info.value.status_code == 404
