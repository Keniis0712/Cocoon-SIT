import pytest
from fastapi import HTTPException

from app.models import User, UserGroup, UserGroupMember
from app.schemas.access.groups import GroupCreate, GroupMemberCreate, GroupUpdate
from app.services.access.group_service import GroupService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_group_service_crud_and_membership_paths():
    session_factory = _session_factory()
    service = GroupService()

    with session_factory() as session:
        owner = User(username="owner", password_hash="hash")
        member = User(username="member", password_hash="hash")
        session.add_all([owner, member])
        session.commit()
        owner_id = owner.id
        member_id = member.id

    with session_factory() as session:
        owner = session.get(User, owner_id)
        assert owner is not None

        created = service.create_group(session, GroupCreate(name="group-a"), owner)
        updated = service.update_group(session, created.id, GroupUpdate(name="group-b"))
        first_member = service.add_group_member(
            session,
            created.id,
            GroupMemberCreate(user_id=member_id, member_role="member"),
        )
        second_member = service.add_group_member(
            session,
            created.id,
            GroupMemberCreate(user_id=member_id, member_role="admin"),
        )

        assert updated.name == "group-b"
        assert second_member.id == first_member.id
        assert [item.id for item in service.list_groups(session)] == [created.id]
        assert [item.user_id for item in service.list_group_members(session, created.id)] == [member_id]

        removed = service.remove_group_member(session, created.id, member_id)
        deleted = service.delete_group(session, created.id)

        assert removed.user_id == member_id
        assert deleted.id == created.id
        assert session.get(UserGroup, created.id) is None
        assert not list(session.query(UserGroupMember).filter(UserGroupMember.group_id == created.id).all())


def test_group_service_raises_for_missing_group_and_member():
    session_factory = _session_factory()
    service = GroupService()

    with session_factory() as session:
        with pytest.raises(HTTPException) as missing_update:
            service.update_group(session, "missing", GroupUpdate(name="x"))
        assert missing_update.value.status_code == 404

        with pytest.raises(HTTPException) as missing_delete:
            service.delete_group(session, "missing")
        assert missing_delete.value.status_code == 404

        with pytest.raises(HTTPException) as missing_group_member:
            service.add_group_member(session, "missing", GroupMemberCreate(user_id="user-1", member_role="member"))
        assert missing_group_member.value.status_code == 404

        with pytest.raises(HTTPException) as missing_remove:
            service.remove_group_member(session, "missing", "user-1")
        assert missing_remove.value.status_code == 404
