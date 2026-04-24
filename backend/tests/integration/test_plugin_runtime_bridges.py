from __future__ import annotations

import io
import json
import time
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.models import (
    ActionDispatch,
    Message,
    PluginDefinition,
    PluginDispatchRecord,
    PluginImDeliveryOutbox,
    PluginRunState,
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


def test_daemon_external_and_im_plugins_start_and_report_state(
    client, auth_headers, default_cocoon_id
):
    daemon_response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "daemon-external",
            "version": "1.0.0",
            "display_name": "Daemon External",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "daemon_one",
                    "mode": "daemon",
                    "function_name": "daemon_one",
                    "title": "Daemon One",
                    "description": "First daemon",
                    "config_schema": {"type": "object"},
                },
                {
                    "name": "daemon_two",
                    "mode": "daemon",
                    "function_name": "daemon_two",
                    "title": "Daemon Two",
                    "description": "Second daemon",
                    "config_schema": {"type": "object"},
                },
            ],
        },
        sources={
            "main.py": """
import asyncio

async def daemon_one(ctx):
    ctx.emit_event({
        "summary": "daemon wakeup one",
        "payload": {"event": "one"}
    })
    while True:
        await asyncio.sleep(0.2)

async def daemon_two(ctx):
    ctx.heartbeat()
    while True:
        await asyncio.sleep(0.2)
""",
        },
    )
    assert daemon_response.status_code == 200, daemon_response.text
    daemon_id = daemon_response.json()["id"]
    _bind_plugin_target(
        client, auth_headers, daemon_id, target_type="cocoon", target_id=default_cocoon_id
    )
    assert (
        client.post(f"/api/v1/admin/plugins/{daemon_id}/enable", headers=auth_headers).status_code
        == 200
    )

    im_response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "sample-im",
            "version": "1.0.0",
            "display_name": "Sample IM",
            "plugin_type": "im",
            "entry_module": "main",
            "service_function": "run",
        },
        sources={
            "main.py": """
import asyncio

async def run(ctx):
    ctx.heartbeat()
    while True:
        await asyncio.sleep(0.2)
""",
        },
    )
    assert im_response.status_code == 200, im_response.text
    im_id = im_response.json()["id"]
    assert (
        client.post(f"/api/v1/admin/plugins/{im_id}/enable", headers=auth_headers).status_code
        == 200
    )

    container = client.app.state.container
    deadline = time.time() + 5
    found_dispatch = False
    while time.time() < deadline:
        time.sleep(0.3)
        container.plugin_runtime_manager.run_once()
        with container.session_factory() as session:
            dispatch = session.scalar(
                select(PluginDispatchRecord).where(
                    PluginDispatchRecord.plugin_id == daemon_id,
                    PluginDispatchRecord.event_name == "daemon_one",
                )
            )
            daemon_state = session.scalar(
                select(PluginRunState).where(PluginRunState.plugin_id == daemon_id)
            )
            im_state = session.scalar(
                select(PluginRunState).where(PluginRunState.plugin_id == im_id)
            )
            if (
                dispatch
                and daemon_state
                and daemon_state.status == "running"
                and daemon_state.pid
                and im_state
                and im_state.status == "running"
                and im_state.pid
            ):
                found_dispatch = True
                break
    assert found_dispatch

    disable_response = client.post(
        f"/api/v1/admin/plugins/{daemon_id}/disable", headers=auth_headers
    )
    assert disable_response.status_code == 200, disable_response.text


def test_im_plugin_bridges_inbound_chat_and_outbound_reply(
    client, auth_headers, default_cocoon_id, worker_runtime
):
    response = _install_response(
        client,
        auth_headers,
        manifest={
            "name": "bridge-im",
            "version": "1.0.0",
            "display_name": "Bridge IM",
            "plugin_type": "im",
            "entry_module": "main",
            "service_function": "run",
            "config_schema": {
                "type": "object",
                "required": ["target_cocoon_id"],
                "properties": {
                    "target_cocoon_id": {"type": "string"},
                },
            },
            "default_config": {"target_cocoon_id": default_cocoon_id},
        },
        sources={
            "main.py": """
import asyncio
import json
from pathlib import Path

from app.services.plugins.im_sdk import ImDeliveryResult, ImInboundRoute, ImPrivateMessage


async def run(ctx):
    @ctx.on_outbound_reply
    async def handle_reply(reply):
        path = Path(ctx.data_dir) / "delivered.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            payload = {"delivery_id": reply.delivery_id, "reply_text": reply.reply_text}
            fh.write(json.dumps(payload, ensure_ascii=False) + "\\n")
        return ImDeliveryResult(ok=True)

    route = ImInboundRoute(
        target_type="cocoon",
        target_id=str(ctx.plugin_config["target_cocoon_id"]),
    )
    message = ImPrivateMessage(
        account_id="acct-1",
        conversation_id="conv-1",
        sender_id="sender-1",
        sender_display_name="Alice",
        text="hello from im",
        message_id="ext-msg-1",
        occurred_at="2026-04-23T00:00:00+00:00",
    )
    await ctx.emit_private_message(route, message)
    await ctx.emit_private_message(route, message)
    await ctx.run_forever(poll_interval_seconds=0.1)
""",
        },
    )
    assert response.status_code == 200, response.text
    plugin_id = response.json()["id"]
    assert (
        client.post(f"/api/v1/admin/plugins/{plugin_id}/enable", headers=auth_headers).status_code
        == 200
    )

    container = client.app.state.container
    delivered_payload = None
    deadline = time.time() + 8
    while time.time() < deadline:
        time.sleep(0.2)
        container.plugin_runtime_manager.run_once()
        worker_runtime.process_next_chat_dispatch()
        container.plugin_runtime_manager.run_once()
        with container.session_factory() as session:
            actions = list(
                session.scalars(
                    select(ActionDispatch)
                    .where(ActionDispatch.cocoon_id == default_cocoon_id)
                    .order_by(ActionDispatch.created_at.asc())
                ).all()
            )
            user_messages = list(
                session.scalars(
                    select(Message)
                    .where(Message.cocoon_id == default_cocoon_id, Message.role == "user")
                    .order_by(Message.created_at.asc())
                ).all()
            )
            assistant_messages = list(
                session.scalars(
                    select(Message)
                    .where(
                        Message.cocoon_id == default_cocoon_id,
                        Message.role == "assistant",
                    )
                    .order_by(Message.created_at.asc())
                ).all()
            )
            outbox = session.scalar(
                select(PluginImDeliveryOutbox).where(PluginImDeliveryOutbox.plugin_id == plugin_id)
            )
            plugin = session.get(PluginDefinition, plugin_id)
            assert plugin is not None
            delivered_path = Path(plugin.data_dir) / "delivered.jsonl"
            if delivered_path.exists():
                delivered_payload = [
                    json.loads(line)
                    for line in delivered_path.read_text(encoding="utf-8").splitlines()
                    if line
                ]
            if (
                len(actions) == 1
                and actions[0].payload_json.get("source_kind") == "plugin_im"
                and actions[0].payload_json.get("source_plugin_id") == plugin_id
                and len(user_messages) == 1
                and user_messages[0].content == "hello from im"
                and assistant_messages
                and outbox is not None
                and outbox.status == "delivered"
                and delivered_payload
            ):
                break

    assert delivered_payload, "Expected IM reply delivery file to be written"
    assert len(delivered_payload) == 1
    assert delivered_payload[0]["reply_text"]
