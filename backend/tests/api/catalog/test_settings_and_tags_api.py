from sqlalchemy import select

from app.models import MemoryChunk, Message, SessionState, TagRegistry


def test_delete_tag_scrubs_bindings_and_cached_tag_arrays(client, auth_headers, default_cocoon_id):
    create = client.post(
        "/api/v1/tags",
        headers=auth_headers,
        json={
            "tag_id": "delete-me",
            "brief": "Delete me",
            "meta_json": {"priority": 1},
        },
    )
    assert create.status_code == 200, create.text
    tag = create.json()

    bind = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/tags",
        headers=auth_headers,
        json={"tag_id": tag["id"]},
    )
    assert bind.status_code == 200, bind.text

    container = client.app.state.container
    with container.session_factory() as session:
        message = Message(
            cocoon_id=default_cocoon_id,
            role="assistant",
            content="tagged message",
            tags_json=[tag["id"]],
        )
        memory = MemoryChunk(
            cocoon_id=default_cocoon_id,
            scope="summary",
            content="tagged memory",
            tags_json=[tag["id"]],
        )
        session.add(message)
        session.add(memory)
        session.flush()
        session_state = session.get(SessionState, default_cocoon_id)
        session_state.active_tags_json = [tag["id"]]
        session.commit()

    deleted = client.delete(f"/api/v1/tags/{tag['id']}", headers=auth_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["tag_id"] == "delete-me"

    with container.session_factory() as session:
        assert session.scalar(select(TagRegistry).where(TagRegistry.id == tag["id"])) is None
        state = session.get(SessionState, default_cocoon_id)
        assert tag["id"] not in state.active_tags_json
        stored_message = session.scalar(select(Message).where(Message.content == "tagged message"))
        stored_memory = session.scalar(select(MemoryChunk).where(MemoryChunk.content == "tagged memory"))
        assert stored_message is not None and tag["id"] not in stored_message.tags_json
        assert stored_memory is not None and tag["id"] not in stored_memory.tags_json


def test_system_settings_drive_public_features_and_registration(client, auth_headers):
    model_id = client.get("/api/v1/providers/models", headers=auth_headers).json()[0]["id"]

    current = client.get("/api/v1/settings", headers=auth_headers)
    assert current.status_code == 200, current.text
    assert "allow_registration" in current.json()

    updated = client.put(
        "/api/v1/settings",
        headers=auth_headers,
        json={
            "allow_registration": True,
            "max_chat_turns": 24,
            "allowed_model_ids": [model_id],
            "default_cocoon_temperature": 0.55,
            "default_max_context_messages": 18,
            "default_auto_compaction_enabled": False,
            "private_chat_debounce_seconds": 5,
            "rollback_retention_days": 14,
            "rollback_cleanup_interval_hours": 12,
        },
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["allow_registration"] is True
    assert payload["allowed_model_ids"] == [model_id]
    assert payload["private_chat_debounce_seconds"] == 5

    features = client.get("/api/v1/auth/features")
    assert features.status_code == 200, features.text
    assert features.json()["allow_registration"] is True
    assert features.json()["allowed_models"][0]["id"] == model_id

    invite = client.post(
        "/api/v1/invites",
        headers=auth_headers,
        json={
            "code": "REGI1234",
            "quota_total": 1,
            "registration_group_id": "root-group",
            "source_type": "ADMIN_OVERRIDE",
        },
    )
    assert invite.status_code == 200, invite.text

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "username": "new-user",
            "password": "new-user-password",
            "email": "new-user@example.com",
            "invite_code": "REGI1234",
        },
    )
    assert registered.status_code == 200, registered.text
    tokens = registered.json()
    assert {"access_token", "refresh_token", "token_type"} <= set(tokens.keys())

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200, me.text
    assert me.json()["username"] == "new-user"
