from __future__ import annotations

import io
import json
import time
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.models import (
    ChatGroupRoom,
    Cocoon,
    PluginDispatchRecord,
    SessionState,
    User,
    WakeupTask,
)

pytestmark = pytest.mark.integration


def _plugin_zip(*, manifest: dict, sources: dict[str, str]) -> io.BytesIO:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as bundle:
        bundle.writestr("plugin.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path, content in sources.items():
            bundle.writestr(path, content)
    buffer.seek(0)
    return buffer


def _install_response(client, auth_headers, *, manifest: dict, sources: dict[str, str]):
    payload = _plugin_zip(manifest=manifest, sources=sources)
    return client.post(
        "/api/v1/admin/plugins/install",
        headers=auth_headers,
        files={"file": ("plugin.zip", payload.getvalue(), "application/zip")},
    )


def _bind_plugin_target(client, auth_headers, plugin_id: str, *, target_type: str, target_id: str):
    response = client.post(
        f"/api/v1/plugins/{plugin_id}/targets",
        headers=auth_headers,
        json={"target_type": target_type, "target_id": target_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_install_external_plugin_and_short_lived_wakeup(client, auth_headers, default_cocoon_id):
    response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "sample-external",
            "version": "1.0.0",
            "display_name": "Sample External",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "sample_short",
                    "mode": "short_lived",
                    "function_name": "sample_short",
                    "title": "Sample Short",
                    "description": "Short-lived external event",
                    "config_schema": {"type": "object"},
                    "default_config": {},
                }
            ],
        },
        sources={
            "main.py": """
def sample_short(ctx):
    return {
        "summary": "short-lived wakeup",
        "payload": {"source": "test"}
    }
""",
        },
    )
    assert response.status_code == 200, response.text
    plugin_id = response.json()["id"]
    _bind_plugin_target(
        client, auth_headers, plugin_id, target_type="cocoon", target_id=default_cocoon_id
    )

    enable_response = client.post(f"/api/v1/admin/plugins/{plugin_id}/enable", headers=auth_headers)
    assert enable_response.status_code == 200, enable_response.text

    container = client.app.state.container
    container.plugin_runtime_manager.run_short_lived_event_now(plugin_id, "sample_short")
    time.sleep(0.5)
    container.plugin_runtime_manager.run_once()

    with container.session_factory() as session:
        dispatch = session.scalar(
            select(PluginDispatchRecord).where(PluginDispatchRecord.plugin_id == plugin_id)
        )
        wakeup = session.scalar(select(WakeupTask).where(WakeupTask.reason == "short-lived wakeup"))
        assert dispatch is not None
        assert wakeup is not None
        assert wakeup.cocoon_id == default_cocoon_id


def test_external_plugin_can_target_chat_group(client, auth_headers):
    container = client.app.state.container
    with container.session_factory() as session:
        admin = session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        default_cocoon = session.scalar(select(Cocoon).limit(1))
        assert default_cocoon is not None
        room = ChatGroupRoom(
            name="Plugin Group",
            owner_user_id=admin.id,
            character_id=default_cocoon.character_id,
            selected_model_id=default_cocoon.selected_model_id,
        )
        session.add(room)
        session.flush()
        session.add(SessionState(chat_group_id=room.id, persona_json={}, active_tags_json=[]))
        session.commit()
        room_id = room.id

    response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "group-external",
            "version": "1.0.0",
            "display_name": "Group External",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "group_short",
                    "mode": "short_lived",
                    "function_name": "group_short",
                    "title": "Group Short",
                    "description": "Chat-group wakeup",
                    "config_schema": {"type": "object"},
                }
            ],
        },
        sources={
            "main.py": """
def group_short(ctx):
    return {
        "summary": "group wakeup",
        "payload": {"kind": "group"}
    }
""",
        },
    )
    assert response.status_code == 200, response.text
    plugin_id = response.json()["id"]
    _bind_plugin_target(
        client, auth_headers, plugin_id, target_type="chat_group", target_id=room_id
    )
    assert (
        client.post(f"/api/v1/admin/plugins/{plugin_id}/enable", headers=auth_headers).status_code
        == 200
    )

    container.plugin_runtime_manager.run_short_lived_event_now(plugin_id, "group_short")
    time.sleep(0.5)
    container.plugin_runtime_manager.run_once()

    with container.session_factory() as session:
        wakeup = session.scalar(select(WakeupTask).where(WakeupTask.chat_group_id == room_id))
        assert wakeup is not None
        assert wakeup.reason == "group wakeup"
