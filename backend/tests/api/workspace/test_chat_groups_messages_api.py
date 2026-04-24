from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.models import (
    Message,
    Role,
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


def test_chat_group_message_routes_cover_listing_dispatch_and_retraction_permissions(
    client,
    auth_headers,
    monkeypatch,
):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    with container.session_factory() as session:
        admin = session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        role = Role(
            name="chat-group-member-role",
            permissions_json={"cocoons:read": True, "cocoons:write": True},
        )
        session.add(role)
        session.flush()
        member = User(
            username="chat-group-member-user",
            email="chat-group-member-user@example.com",
            password_hash=hash_secret("secret"),
            role_id=role.id,
        )
        session.add(member)
        session.flush()
        member_id = member.id
        admin_id = admin.id
        session.commit()

    create_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={
            "name": "Message Group",
            "character_id": character_id,
            "selected_model_id": model_id,
            "initial_member_ids": [member_id],
        },
    )
    assert create_response.status_code == 200, create_response.text
    room_id = create_response.json()["id"]

    with container.session_factory() as session:
        user_message = Message(
            chat_group_id=room_id,
            role="user",
            sender_user_id=admin_id,
            content="Admin authored message",
        )
        assistant_message = Message(
            chat_group_id=room_id, role="assistant", content="Assistant authored message"
        )
        session.add_all([user_message, assistant_message])
        session.commit()
        user_message_id = user_message.id
        assistant_message_id = assistant_message.id

    list_response = client.get(f"/api/v1/chat-groups/{room_id}/messages", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert {item["id"] for item in list_response.json()} >= {user_message_id, assistant_message_id}

    debounce_until = datetime.now(UTC) + timedelta(seconds=30)
    monkeypatch_payload = SimpleNamespace(
        id="chat-group-action", status="queued", debounce_until=debounce_until
    )
    monkeypatch.setattr(
        container.message_dispatch_service,
        "enqueue_chat_group_message",
        lambda *args, **kwargs: monkeypatch_payload,
    )
    send_response = client.post(
        f"/api/v1/chat-groups/{room_id}/messages",
        headers=auth_headers,
        json={"content": "queued", "client_request_id": "chat-group-message-1", "timezone": "UTC"},
    )
    assert send_response.status_code == 202, send_response.text
    assert send_response.json()["action_id"] == "chat-group-action"
    assert send_response.json()["debounce_until"] == int(debounce_until.timestamp())

    member_headers = _login_headers(client, "chat-group-member-user")

    foreign_user_retract = client.post(
        f"/api/v1/chat-groups/{room_id}/messages/{user_message_id}/retract",
        headers=member_headers,
    )
    assert foreign_user_retract.status_code == 403, foreign_user_retract.text
    foreign_retract_payload = foreign_user_retract.json()
    assert foreign_retract_payload["code"] == "CANNOT_RETRACT_THIS_MESSAGE"
    assert foreign_retract_payload["msg"] == "Cannot retract this message"
    assert foreign_retract_payload["data"] is None

    assistant_retract = client.post(
        f"/api/v1/chat-groups/{room_id}/messages/{assistant_message_id}/retract",
        headers=member_headers,
    )
    assert assistant_retract.status_code == 403, assistant_retract.text
    assistant_retract_payload = assistant_retract.json()
    assert assistant_retract_payload["code"] == "CANNOT_RETRACT_AI_MESSAGE"
    assert assistant_retract_payload["msg"] == "Cannot retract AI message"
    assert assistant_retract_payload["data"] is None

    admin_retract = client.post(
        f"/api/v1/chat-groups/{room_id}/messages/{assistant_message_id}/retract",
        headers=auth_headers,
    )
    assert admin_retract.status_code == 200, admin_retract.text
    assert admin_retract.json()["message_id"] == assistant_message_id
    assert admin_retract.json()["is_retracted"] is True
