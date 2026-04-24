from datetime import UTC, datetime

from app.models import (
    ActionDispatch,
    Message,
    PluginDefinition,
    PluginDispatchRecord,
    PluginImDeliveryOutbox,
    PluginVersion,
    WakeupTask,
)


def _default_character_and_model_ids(client, auth_headers):
    characters = client.get("/api/v1/characters", headers=auth_headers).json()
    models = client.get("/api/v1/providers/models", headers=auth_headers).json()
    return characters[0]["id"], models[0]["id"]


def _login_headers(client, username: str, password: str = "secret") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_delete_chat_group_cleans_plugin_dispatch_records_for_wakeups(client, auth_headers):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={
            "name": "Cleanup Group Plugin Dispatch",
            "character_id": character_id,
            "selected_model_id": model_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    room_id = create_response.json()["id"]

    with container.session_factory() as session:
        plugin = PluginDefinition(
            name="cleanup-group-plugin",
            display_name="Cleanup Group Plugin",
            plugin_type="external",
            entry_module="main",
            status="enabled",
            data_dir="data/plugins/cleanup-group-plugin",
        )
        session.add(plugin)
        session.flush()
        version = PluginVersion(
            plugin_id=plugin.id,
            version="1.0.0",
            source_zip_path="cleanup-group.zip",
            extracted_path="cleanup-group",
            manifest_path="cleanup-group/plugin.json",
        )
        session.add(version)
        session.flush()
        plugin.active_version_id = version.id
        wakeup = WakeupTask(
            chat_group_id=room_id,
            run_at=datetime.now(UTC).replace(tzinfo=None),
            reason="room wakeup with dispatch",
            payload_json={},
        )
        session.add(wakeup)
        session.flush()
        dispatch = PluginDispatchRecord(
            plugin_id=plugin.id,
            plugin_version_id=version.id,
            event_name="tick",
            target_type="chat_group",
            target_id=room_id,
            wakeup_task_id=wakeup.id,
            payload_json={},
        )
        session.add(dispatch)
        session.commit()
        wakeup_id = wakeup.id
        dispatch_id = dispatch.id

    delete_response = client.delete(f"/api/v1/chat-groups/{room_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text

    with container.session_factory() as session:
        assert session.get(WakeupTask, wakeup_id) is None
        assert session.get(PluginDispatchRecord, dispatch_id) is None


def test_delete_chat_group_cleans_plugin_im_delivery_outbox_records(client, auth_headers):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={
            "name": "Cleanup Group IM Outbox",
            "character_id": character_id,
            "selected_model_id": model_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    room_id = create_response.json()["id"]

    with container.session_factory() as session:
        plugin = PluginDefinition(
            name="cleanup-group-im-plugin",
            display_name="Cleanup Group IM Plugin",
            plugin_type="im",
            entry_module="main",
            service_function_name="run",
            status="enabled",
            data_dir="data/plugins/cleanup-group-im-plugin",
        )
        session.add(plugin)
        session.flush()
        version = PluginVersion(
            plugin_id=plugin.id,
            version="1.0.0",
            source_zip_path="cleanup-group-im.zip",
            extracted_path="cleanup-group-im",
            manifest_path="cleanup-group-im/plugin.json",
        )
        session.add(version)
        session.flush()
        plugin.active_version_id = version.id

        action = ActionDispatch(
            chat_group_id=room_id, event_type="chat", status="completed", payload_json={}
        )
        session.add(action)
        session.flush()

        message = Message(
            chat_group_id=room_id,
            action_id=action.id,
            role="assistant",
            content="Delete room outbox",
        )
        session.add(message)
        session.flush()

        outbox = PluginImDeliveryOutbox(
            plugin_id=plugin.id,
            action_id=action.id,
            message_id=message.id,
            status="delivered",
            payload_json={"reply_text": "Delete room outbox"},
        )
        session.add(outbox)
        session.commit()
        outbox_id = outbox.id
        message_id = message.id
        action_id = action.id

    delete_response = client.delete(f"/api/v1/chat-groups/{room_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text

    with container.session_factory() as session:
        assert session.get(PluginImDeliveryOutbox, outbox_id) is None
        assert session.get(Message, message_id) is None
        assert session.get(ActionDispatch, action_id) is None
