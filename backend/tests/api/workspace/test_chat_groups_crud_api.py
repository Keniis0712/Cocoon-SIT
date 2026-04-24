from sqlalchemy import select

from app.models import (
    SessionState,
    User,
)
from app.services.security.encryption import hash_secret


def _default_character_and_model_ids(client, auth_headers):
    characters = client.get("/api/v1/characters", headers=auth_headers).json()
    models = client.get("/api/v1/providers/models", headers=auth_headers).json()
    return characters[0]["id"], models[0]["id"]


def _login_headers(client, username: str, password: str = "secret") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_chat_group_routes_support_crud_members_and_state(client, auth_headers):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    with container.session_factory() as session:
        extra_user = User(
            username="group-member",
            email="group-member@example.com",
            password_hash=hash_secret("secret"),
        )
        removable_user = User(
            username="group-removable",
            email="group-removable@example.com",
            password_hash=hash_secret("secret"),
        )
        admin = session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        session.add_all([extra_user, removable_user])
        session.commit()
        extra_user_id = extra_user.id
        removable_user_id = removable_user.id
        admin_id = admin.id

    create_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={
            "name": "API Group",
            "character_id": character_id,
            "selected_model_id": model_id,
            "initial_member_ids": [extra_user_id, extra_user_id, admin_id],
        },
    )
    assert create_response.status_code == 200, create_response.text
    room_id = create_response.json()["id"]

    list_response = client.get("/api/v1/chat-groups", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == room_id for item in list_response.json())

    get_response = client.get(f"/api/v1/chat-groups/{room_id}", headers=auth_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["id"] == room_id

    update_response = client.patch(
        f"/api/v1/chat-groups/{room_id}",
        headers=auth_headers,
        json={
            "name": "API Group Updated",
            "character_id": character_id,
            "external_platform": "discord",
            "external_group_id": "room-42",
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["name"] == "API Group Updated"
    assert update_response.json()["external_platform"] == "discord"

    members_response = client.get(f"/api/v1/chat-groups/{room_id}/members", headers=auth_headers)
    assert members_response.status_code == 200, members_response.text
    assert {item["user_id"] for item in members_response.json()} == {admin_id, extra_user_id}

    add_member = client.post(
        f"/api/v1/chat-groups/{room_id}/members",
        headers=auth_headers,
        json={"user_id": removable_user_id, "member_role": "member"},
    )
    assert add_member.status_code == 200, add_member.text

    update_member = client.patch(
        f"/api/v1/chat-groups/{room_id}/members/{removable_user_id}",
        headers=auth_headers,
        json={"member_role": "admin"},
    )
    assert update_member.status_code == 200, update_member.text
    assert update_member.json()["member_role"] == "admin"

    remove_member = client.delete(
        f"/api/v1/chat-groups/{room_id}/members/{removable_user_id}", headers=auth_headers
    )
    assert remove_member.status_code == 200, remove_member.text
    assert remove_member.json()["user_id"] == removable_user_id

    state_response = client.get(f"/api/v1/chat-groups/{room_id}/state", headers=auth_headers)
    assert state_response.status_code == 200, state_response.text
    assert state_response.json()["chat_group_id"] == room_id


def test_chat_group_owner_constraints_and_state_404(client, auth_headers):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={
            "name": "Owner Constraint Group",
            "character_id": character_id,
            "selected_model_id": model_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    room_id = create_response.json()["id"]
    owner_user_id = create_response.json()["owner_user_id"]

    with container.session_factory() as session:
        state = session.get(SessionState, room_id)
        assert state is not None
        session.delete(state)
        session.commit()

    state_response = client.get(f"/api/v1/chat-groups/{room_id}/state", headers=auth_headers)
    assert state_response.status_code == 404, state_response.text

    owner_update = client.patch(
        f"/api/v1/chat-groups/{room_id}/members/{owner_user_id}",
        headers=auth_headers,
        json={"member_role": "member"},
    )
    assert owner_update.status_code == 400, owner_update.text

    owner_remove = client.delete(
        f"/api/v1/chat-groups/{room_id}/members/{owner_user_id}", headers=auth_headers
    )
    assert owner_remove.status_code == 400, owner_remove.text
