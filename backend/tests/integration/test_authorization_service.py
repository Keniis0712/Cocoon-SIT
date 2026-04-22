import pytest
from sqlalchemy import select

from app.models import (
    Character,
    CharacterAcl,
    Cocoon,
    Role,
    SessionState,
    User,
    UserGroup,
    UserGroupMember,
)
from app.services.security.encryption import hash_secret

pytestmark = pytest.mark.integration


def _create_user(session, username: str, role_id: str | None = None) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_secret("secret"),
        role_id=role_id,
    )
    session.add(user)
    session.flush()
    return user


def _login_headers(client, username: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "secret"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_authorization_service_supports_owner_user_role_and_group_rules(client):
    container = client.app.state.container

    with container.session_factory() as session:
        admin = session.scalar(select(User).where(User.username == "admin"))
        model = session.scalar(select(Cocoon.selected_model_id).limit(1))
        assert admin is not None
        assert model is not None

        viewer_role = Role(name="viewer-acl", permissions_json={"cocoons:read": True, "characters:read": True})
        session.add(viewer_role)
        session.flush()

        role_user = _create_user(session, "role-user", viewer_role.id)
        direct_user = _create_user(session, "direct-user")
        group_user = _create_user(session, "group-user")
        owner_user = _create_user(session, "owner-user")
        stranger = _create_user(session, "stranger-user")

        group = UserGroup(name="qa-shared", owner_user_id=admin.id)
        session.add(group)
        session.flush()
        session.add(UserGroupMember(group_id=group.id, user_id=group_user.id, member_role="member"))

        role_character = Character(name="Role Character", prompt_summary="role", settings_json={}, created_by_user_id=admin.id)
        direct_character = Character(name="Direct Character", prompt_summary="direct", settings_json={}, created_by_user_id=admin.id)
        group_character = Character(name="Group Character", prompt_summary="group", settings_json={}, created_by_user_id=admin.id)
        session.add_all([role_character, direct_character, group_character])
        session.flush()

        session.add_all(
            [
                CharacterAcl(character_id=role_character.id, subject_type="role", subject_id=viewer_role.id, can_read=True, can_use=True),
                CharacterAcl(character_id=direct_character.id, subject_type="user", subject_id=direct_user.id, can_read=True, can_use=True),
                CharacterAcl(character_id=group_character.id, subject_type="group", subject_id=group.id, can_read=True, can_use=True),
            ]
        )

        owner_cocoon = Cocoon(
            name="Owner Cocoon",
            owner_user_id=owner_user.id,
            character_id=role_character.id,
            selected_model_id=model,
        )
        session.add(owner_cocoon)
        session.flush()
        session.add(SessionState(cocoon_id=owner_cocoon.id, persona_json={}, active_tags_json=[]))
        session.commit()

    with container.session_factory() as session:
        authz = container.authorization_service
        assert authz.can_read_character(session, role_user, session.get(Character, role_character.id))
        assert authz.can_read_character(session, direct_user, session.get(Character, direct_character.id))
        assert authz.can_read_character(session, group_user, session.get(Character, group_character.id))
        assert authz.can_access_cocoon(session, owner_user, session.get(Cocoon, owner_cocoon.id), write=True)
        assert authz.can_read_character(session, stranger, session.get(Character, role_character.id)) is False


def test_cocoon_routes_filter_inaccessible_cocoons(client, auth_headers):
    container = client.app.state.container
    model_id = client.get("/api/v1/providers/models", headers=auth_headers).json()[0]["id"]

    with container.session_factory() as session:
        admin = session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        role = Role(name="route-viewer", permissions_json={"cocoons:read": True, "characters:read": True})
        session.add(role)
        session.flush()
        user = _create_user(session, "route-viewer-user", role.id)

        visible_character = Character(name="Visible Character", prompt_summary="", settings_json={}, created_by_user_id=admin.id)
        hidden_character = Character(name="Hidden Character", prompt_summary="", settings_json={}, created_by_user_id=admin.id)
        session.add_all([visible_character, hidden_character])
        session.flush()
        session.add(CharacterAcl(character_id=visible_character.id, subject_type="role", subject_id=role.id, can_read=True, can_use=True))

        visible_cocoon = Cocoon(
            name="Visible Cocoon",
            owner_user_id=admin.id,
            character_id=visible_character.id,
            selected_model_id=model_id,
        )
        hidden_cocoon = Cocoon(
            name="Hidden Cocoon",
            owner_user_id=admin.id,
            character_id=hidden_character.id,
            selected_model_id=model_id,
        )
        session.add_all([visible_cocoon, hidden_cocoon])
        session.flush()
        session.add_all(
            [
                SessionState(cocoon_id=visible_cocoon.id, persona_json={}, active_tags_json=[]),
                SessionState(cocoon_id=hidden_cocoon.id, persona_json={}, active_tags_json=[]),
            ]
        )
        session.commit()

    viewer_headers = _login_headers(client, "route-viewer-user")
    response = client.get("/api/v1/cocoons", headers=viewer_headers)
    assert response.status_code == 200, response.text
    names = {item["name"] for item in response.json()}
    assert "Visible Cocoon" in names
    assert "Hidden Cocoon" not in names
