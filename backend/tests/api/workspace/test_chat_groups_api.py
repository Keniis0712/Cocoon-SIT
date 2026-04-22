from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.models import (
    ActionDispatch,
    AuditArtifact,
    AuditLink,
    AuditRun,
    AuditStep,
    ChatGroupRoom,
    DurableJob,
    FailedRound,
    MemoryChunk,
    Message,
    Role,
    SessionState,
    User,
    WakeupTask,
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

    remove_member = client.delete(f"/api/v1/chat-groups/{room_id}/members/{removable_user_id}", headers=auth_headers)
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
        json={"name": "Owner Constraint Group", "character_id": character_id, "selected_model_id": model_id},
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

    owner_remove = client.delete(f"/api/v1/chat-groups/{room_id}/members/{owner_user_id}", headers=auth_headers)
    assert owner_remove.status_code == 400, owner_remove.text


def test_delete_chat_group_cleans_related_records(client, auth_headers):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={"name": "Cleanup Group", "character_id": character_id, "selected_model_id": model_id},
    )
    assert create_response.status_code == 200, create_response.text
    room_id = create_response.json()["id"]

    with container.session_factory() as session:
        action = ActionDispatch(chat_group_id=room_id, event_type="chat", status="completed", payload_json={})
        session.add(action)
        session.flush()

        message = Message(chat_group_id=room_id, action_id=action.id, role="assistant", content="Delete me")
        session.add(message)
        session.flush()

        memory = MemoryChunk(chat_group_id=room_id, source_message_id=message.id, scope="dialogue", content="Delete memory")
        session.add(memory)
        session.flush()

        job = DurableJob(chat_group_id=room_id, job_type="wakeup", lock_key="room-cleanup", payload_json={})
        session.add(job)
        session.flush()
        session.add(
            WakeupTask(
                chat_group_id=room_id,
                run_at=datetime.now(UTC).replace(tzinfo=None),
                reason="room wakeup",
                payload_json={},
            )
        )

        run = AuditRun(chat_group_id=room_id, action_id=action.id, operation_type="chat")
        session.add(run)
        session.flush()
        step = AuditStep(run_id=run.id, step_name="generator")
        session.add(step)
        session.flush()
        artifact = AuditArtifact(run_id=run.id, step_id=step.id, kind="generator_output", metadata_json={})
        session.add(artifact)
        session.flush()
        session.add(
            AuditLink(
                run_id=run.id,
                source_step_id=step.id,
                target_artifact_id=artifact.id,
                relation="produced_by",
            )
        )
        session.add(FailedRound(chat_group_id=room_id, action_id=action.id, event_type="chat", reason="cleanup"))
        session.commit()

    delete_response = client.delete(f"/api/v1/chat-groups/{room_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["id"] == room_id

    with container.session_factory() as session:
        assert session.get(ChatGroupRoom, room_id) is None
        assert session.get(SessionState, room_id) is None
        assert session.scalar(select(Message).where(Message.chat_group_id == room_id)) is None
        assert session.scalar(select(MemoryChunk).where(MemoryChunk.chat_group_id == room_id)) is None
        assert session.scalar(select(ActionDispatch).where(ActionDispatch.chat_group_id == room_id)) is None
        assert session.scalar(select(AuditRun).where(AuditRun.chat_group_id == room_id)) is None
        assert session.scalar(select(DurableJob).where(DurableJob.chat_group_id == room_id)) is None
        assert session.scalar(select(WakeupTask).where(WakeupTask.chat_group_id == room_id)) is None


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
        assistant_message = Message(chat_group_id=room_id, role="assistant", content="Assistant authored message")
        session.add_all([user_message, assistant_message])
        session.commit()
        user_message_id = user_message.id
        assistant_message_id = assistant_message.id

    list_response = client.get(f"/api/v1/chat-groups/{room_id}/messages", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert {item["id"] for item in list_response.json()} >= {user_message_id, assistant_message_id}

    debounce_until = datetime.now(UTC) + timedelta(seconds=30)
    monkeypatch_payload = SimpleNamespace(id="chat-group-action", status="queued", debounce_until=debounce_until)
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
    assert foreign_user_retract.json()["detail"] == "Cannot retract this message"

    assistant_retract = client.post(
        f"/api/v1/chat-groups/{room_id}/messages/{assistant_message_id}/retract",
        headers=member_headers,
    )
    assert assistant_retract.status_code == 403, assistant_retract.text
    assert assistant_retract.json()["detail"] == "Cannot retract AI message"

    admin_retract = client.post(
        f"/api/v1/chat-groups/{room_id}/messages/{assistant_message_id}/retract",
        headers=auth_headers,
    )
    assert admin_retract.status_code == 200, admin_retract.text
    assert admin_retract.json()["message_id"] == assistant_message_id
    assert admin_retract.json()["is_retracted"] is True


def test_delete_chat_group_without_actions_cleans_failed_rounds(client, auth_headers):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={"name": "No Action Cleanup Group", "character_id": character_id, "selected_model_id": model_id},
    )
    assert create_response.status_code == 200, create_response.text
    room_id = create_response.json()["id"]

    with container.session_factory() as session:
        session.add(FailedRound(chat_group_id=room_id, action_id=None, event_type="chat", reason="orphan cleanup"))
        session.commit()

    delete_response = client.delete(f"/api/v1/chat-groups/{room_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text

    with container.session_factory() as session:
        assert session.scalar(select(FailedRound).where(FailedRound.chat_group_id == room_id)) is None
