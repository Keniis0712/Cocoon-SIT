import pytest
from fastapi import HTTPException

from app.models import (
    AuditRun,
    Character,
    CharacterAcl,
    ChatGroupMember,
    ChatGroupRoom,
    Cocoon,
    Role,
    SessionState,
    User,
    UserGroup,
    UserGroupMember,
)
from app.services.security.authorization_service import AuthorizationService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_authorization_service_character_cocoon_chat_group_and_audit_rules():
    session_factory = _session_factory()
    service = AuthorizationService()

    with session_factory() as session:
        admin_role = Role(name="admin", permissions_json={})
        viewer_role = Role(name="viewer", permissions_json={})
        session.add_all([admin_role, viewer_role])
        session.flush()

        admin = User(username="admin", password_hash="hash", role_id=admin_role.id)
        owner = User(username="owner", password_hash="hash")
        role_user = User(username="role-user", password_hash="hash", role_id=viewer_role.id)
        direct_user = User(username="direct-user", password_hash="hash")
        group_user = User(username="group-user", password_hash="hash")
        stranger = User(username="stranger", password_hash="hash")
        no_role = User(username="no-role", password_hash="hash")
        session.add_all([admin, owner, role_user, direct_user, group_user, stranger, no_role])
        session.flush()

        group = UserGroup(name="team", owner_user_id=owner.id)
        session.add(group)
        session.flush()
        session.add(UserGroupMember(group_id=group.id, user_id=group_user.id, member_role="member"))

        role_character = Character(name="role", prompt_summary="", settings_json={}, created_by_user_id=owner.id)
        direct_character = Character(name="direct", prompt_summary="", settings_json={}, created_by_user_id=owner.id)
        group_character = Character(name="group", prompt_summary="", settings_json={}, created_by_user_id=owner.id)
        owner_character = Character(name="owner-char", prompt_summary="", settings_json={}, created_by_user_id=owner.id)
        hidden_character = Character(name="hidden", prompt_summary="", settings_json={}, created_by_user_id=owner.id)
        session.add_all([role_character, direct_character, group_character, owner_character, hidden_character])
        session.flush()
        session.add_all(
            [
                CharacterAcl(character_id=role_character.id, subject_type="role", subject_id=viewer_role.id, can_read=True, can_use=True),
                CharacterAcl(character_id=direct_character.id, subject_type="user", subject_id=direct_user.id, can_read=True, can_use=True),
                CharacterAcl(character_id=group_character.id, subject_type="group", subject_id=group.id, can_read=True, can_use=True),
            ]
        )

        cocoon = Cocoon(
            name="visible-cocoon",
            owner_user_id=owner.id,
            character_id=role_character.id,
            selected_model_id="model-1",
        )
        hidden_cocoon = Cocoon(
            name="hidden-cocoon",
            owner_user_id=stranger.id,
            character_id="missing-character",
            selected_model_id="model-1",
        )
        session.add_all([cocoon, hidden_cocoon])
        session.flush()
        session.add(SessionState(cocoon_id=cocoon.id, persona_json={}, active_tags_json=[]))

        room = ChatGroupRoom(
            name="room",
            owner_user_id=owner.id,
            character_id=role_character.id,
            selected_model_id="model-1",
        )
        hidden_room = ChatGroupRoom(
            name="hidden-room",
            owner_user_id=stranger.id,
            character_id=role_character.id,
            selected_model_id="model-1",
        )
        session.add_all([room, hidden_room])
        session.flush()
        session.add_all(
            [
                ChatGroupMember(room_id=room.id, user_id=role_user.id, member_role="admin"),
                ChatGroupMember(room_id=room.id, user_id=direct_user.id, member_role="member"),
            ]
        )

        cocoon_run = AuditRun(cocoon_id=cocoon.id, operation_type="chat")
        room_run = AuditRun(chat_group_id=room.id, operation_type="chat")
        global_run = AuditRun(operation_type="system")
        session.add_all([cocoon_run, room_run, global_run])
        session.commit()

        assert service.is_admin(session, admin) is True
        assert service.is_admin(session, no_role) is False
        assert service.is_admin(session, role_user) is False
        assert service._group_ids_for_user(session, group_user.id) == {group.id}

        assert service.can_read_character(session, admin, hidden_character) is True
        assert service.can_read_character(session, owner, owner_character) is True
        assert service.can_read_character(session, role_user, role_character) is True
        assert service.can_read_character(session, direct_user, direct_character) is True
        assert service.can_read_character(session, group_user, group_character) is True
        assert service.can_read_character(session, stranger, hidden_character) is False

        assert service.can_use_character(session, role_user, role_character) is True
        assert service.can_use_character(session, direct_user, direct_character) is True
        assert service.can_use_character(session, group_user, group_character) is True
        assert service.can_use_character(session, stranger, hidden_character) is False

        assert service.require_character_read(session, role_user, role_character.id).id == role_character.id
        assert service.require_character_use(session, direct_user, direct_character.id).id == direct_character.id
        with pytest.raises(HTTPException) as missing_character:
            service.require_character_read(session, stranger, "missing")
        assert missing_character.value.status_code == 404
        with pytest.raises(HTTPException) as denied_character:
            service.require_character_use(session, stranger, hidden_character.id)
        assert denied_character.value.status_code == 403

        visible_chars = service.filter_visible_characters(session, role_user, [role_character, hidden_character])
        assert [item.id for item in visible_chars] == [role_character.id]

        assert service.can_access_cocoon(session, owner, cocoon, write=True) is True
        assert service.can_access_cocoon(session, role_user, cocoon, write=False) is True
        assert service.can_access_cocoon(session, role_user, cocoon, write=True) is True
        assert service.can_access_cocoon(session, direct_user, hidden_cocoon, write=False) is False

        assert service.require_cocoon_access(session, role_user, cocoon.id, write=False).id == cocoon.id
        with pytest.raises(HTTPException) as missing_cocoon:
            service.require_cocoon_access(session, role_user, "missing", write=False)
        assert missing_cocoon.value.status_code == 404
        with pytest.raises(HTTPException) as denied_cocoon:
            service.require_cocoon_access(session, stranger, cocoon.id, write=False)
        assert denied_cocoon.value.status_code == 403
        assert [item.id for item in service.filter_visible_cocoons(session, role_user, [cocoon, hidden_cocoon])] == [cocoon.id]
        assert service.require_pull_merge_access(session, role_user, source_cocoon_id=cocoon.id, target_cocoon_id=cocoon.id) == (
            cocoon,
            cocoon,
        )

        assert service.get_chat_group_membership(session, role_user.id, room.id).member_role == "admin"
        assert service.get_chat_group_membership(session, stranger.id, room.id) is None
        assert service.can_read_chat_group(session, owner, room) is True
        assert service.can_read_chat_group(session, direct_user, room) is True
        assert service.can_chat_in_chat_group(session, direct_user, room) is True
        assert service.can_manage_chat_group(session, role_user, room) is True
        assert service.can_manage_chat_group(session, direct_user, room) is False

        assert service.require_chat_group_access(session, direct_user, room.id, write=True).id == room.id
        assert service.require_chat_group_access(session, role_user, room.id, manage=True).id == room.id
        assert service.require_chat_group_access(session, owner, room.id, owner=True).id == room.id
        with pytest.raises(HTTPException) as missing_room:
            service.require_chat_group_access(session, owner, "missing")
        assert missing_room.value.status_code == 404
        with pytest.raises(HTTPException) as owner_denied:
            service.require_chat_group_access(session, direct_user, room.id, owner=True)
        assert owner_denied.value.status_code == 403
        with pytest.raises(HTTPException) as manage_denied:
            service.require_chat_group_access(session, direct_user, room.id, manage=True)
        assert manage_denied.value.status_code == 403
        with pytest.raises(HTTPException) as write_denied:
            service.require_chat_group_access(session, stranger, room.id, write=True)
        assert write_denied.value.status_code == 403
        with pytest.raises(HTTPException) as read_denied:
            service.require_chat_group_access(session, stranger, room.id)
        assert read_denied.value.status_code == 403

        assert [item.id for item in service.filter_visible_chat_groups(session, direct_user, [room, hidden_room])] == [room.id]

        assert service.can_view_audit_run(session, role_user, cocoon_run) is True
        assert service.can_view_audit_run(session, direct_user, room_run) is True
        assert service.can_view_audit_run(session, stranger, global_run) is False
        assert service.can_view_audit_run(session, admin, global_run) is True
        visible_runs = service.filter_visible_audit_runs(session, role_user, [cocoon_run, room_run, global_run])
        assert [item.id for item in visible_runs] == [cocoon_run.id, room_run.id]


def test_authorization_service_covers_acl_skips_and_missing_audit_targets():
    session_factory = _session_factory()
    service = AuthorizationService()

    with session_factory() as session:
        role = Role(name="member", permissions_json={})
        session.add(role)
        session.flush()

        owner = User(username="owner-two", password_hash="hash")
        user = User(username="user-two", password_hash="hash")
        session.add_all([owner, user])
        session.flush()

        read_blocked = Character(name="read-blocked", prompt_summary="", settings_json={}, created_by_user_id=owner.id)
        use_blocked = Character(name="use-blocked", prompt_summary="", settings_json={}, created_by_user_id=owner.id)
        owned = Character(name="owned", prompt_summary="", settings_json={}, created_by_user_id=user.id)
        session.add_all([read_blocked, use_blocked, owned])
        session.flush()
        session.add_all(
            [
                CharacterAcl(
                    character_id=read_blocked.id,
                    subject_type="user",
                    subject_id=user.id,
                    can_read=False,
                    can_use=True,
                ),
                CharacterAcl(
                    character_id=use_blocked.id,
                    subject_type="user",
                    subject_id=user.id,
                    can_read=True,
                    can_use=False,
                ),
            ]
        )
        session.commit()

        assert service.can_read_character(session, user, read_blocked) is False
        assert service.can_use_character(session, user, use_blocked) is False
        assert service.can_use_character(session, user, owned) is True
        assert service.can_view_audit_run(session, user, AuditRun(cocoon_id="missing", operation_type="chat")) is False
        assert service.can_view_audit_run(session, user, AuditRun(chat_group_id="missing-room", operation_type="chat")) is False
