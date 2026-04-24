from __future__ import annotations

import asyncio
from queue import Empty

import pytest

from app.services.plugins.im_sdk import (
    ImDeliveryResult,
    ImGroupMessage,
    ImInboundRoute,
    ImPluginContext,
    ImPrivateMessage,
)


class _Queue:
    def __init__(self, items=None):
        self.items = list(items or [])

    def put(self, item):
        self.items.append(item)

    def get(self, block=True, timeout=None):
        if not self.items:
            raise Empty()
        return self.items.pop(0)


def _private_message() -> ImPrivateMessage:
    return ImPrivateMessage(
        account_id="acct-1",
        conversation_id="conv-1",
        sender_id="sender-1",
        sender_display_name="Alice",
        text="hello",
        message_id="msg-1",
        occurred_at="2026-04-24T00:00:00+00:00",
    )


def _group_message() -> ImGroupMessage:
    return ImGroupMessage(
        account_id="acct-1",
        conversation_id="group-1",
        sender_id="sender-1",
        sender_display_name="Alice",
        text="hello group",
        message_id="msg-2",
        occurred_at="2026-04-24T00:00:01+00:00",
        group_name="Group",
    )


def test_im_plugin_context_group_handler_startup_shutdown_and_buffering():
    inbound = _Queue(
        [
            {"type": "rpc_response", "request_id": "other", "ok": True, "payload": {"ignored": True}},
            {"type": "deliver_reply", "delivery_id": "d-1", "reply": {"delivery_id": "d-1", "plugin_id": "plugin", "target_type": "cocoon", "target_id": "c-1", "reply_text": "pong"}},
            {"type": "stop"},
        ]
    )
    outbound = _Queue()
    context = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data/plugin",
        inbound_queue=inbound,
        outbound_queue=outbound,
        heartbeat_interval_seconds=0.0,
    )
    calls = []

    @context.on_startup
    def _startup():
        calls.append("startup")

    @context.on_shutdown
    async def _shutdown():
        calls.append("shutdown")

    @context.on_group_message
    async def _group_handler(message):
        calls.append(("group", message.group_name))
        return {"target_type": "chat_group", "target_id": "room-1", "metadata_json": {"tag": "x"}}

    @context.on_outbound_reply
    async def _reply_handler(reply):
        calls.append(("reply", reply.reply_text))
        return {"ok": True, "retryable": False, "metadata_json": {"sent": True}}

    async def _exercise():
        route = await context.handle_group_message(_group_message())
        assert route is not None
        assert route.target_type == "chat_group"
        await context.run_forever(poll_interval_seconds=0.0)

    asyncio.run(_exercise())

    assert calls[0] == ("group", "Group")
    assert "startup" in calls
    assert "shutdown" in calls
    assert ("reply", "pong") in calls
    assert any(item["type"] == "im_inbound_message" and item["message_kind"] == "group" for item in outbound.items)
    assert any(item["type"] == "heartbeat" for item in outbound.items)
    assert any(
        item["type"] == "delivery_result"
        and item["result"] == {"ok": True, "error": None, "retryable": False, "metadata_json": {"sent": True}}
        for item in outbound.items
    )


def test_im_plugin_context_handles_missing_handlers_and_delivery_exceptions():
    outbound = _Queue()
    context = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data/plugin",
        inbound_queue=_Queue(),
        outbound_queue=outbound,
    )

    async def _exercise():
        assert await context.handle_private_message(_private_message()) is None
        await context._dispatch_outbound_reply({"delivery_id": "d-missing", "reply": {}})

        @context.on_outbound_reply
        async def _raise(reply):
            raise RuntimeError("send failed")

        await context._dispatch_outbound_reply({"delivery_id": "d-error", "reply": {"plugin_id": "plugin"}})

    asyncio.run(_exercise())

    results = [item for item in outbound.items if item["type"] == "delivery_result"]
    assert results[0]["result"]["error"] == "No outbound reply handler registered"
    assert results[1]["result"]["error"] == "send failed"


def test_im_plugin_context_rpc_and_coercion_error_paths():
    context = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data/plugin",
        inbound_queue=_Queue(),
        outbound_queue=_Queue(),
    )

    async def _rpc_failure():
        context._buffered_control_messages = [
            {"type": "rpc_response", "request_id": "wrong", "ok": True, "payload": {}},
        ]
        task = asyncio.create_task(context._rpc("method", {"x": 1}))
        await asyncio.sleep(0)
        request_id = next(item["request_id"] for item in context.outbound_queue.items if item["type"] == "rpc_request")
        context._buffered_control_messages.append(
            {"type": "rpc_response", "request_id": request_id, "ok": False, "error": "bad"}
        )
        with pytest.raises(RuntimeError, match="bad"):
            await task
        assert any(
            item.get("type") == "rpc_response" and item.get("request_id") == "wrong"
            for item in context._buffered_control_messages
        )

    async def _rpc_invalid_payload():
        context._buffered_control_messages = []
        task = asyncio.create_task(context._rpc("other", {}))
        await asyncio.sleep(0)
        request_id = [
            item["request_id"]
            for item in context.outbound_queue.items
            if item["type"] == "rpc_request" and item["method"] == "other"
        ][0]
        context._buffered_control_messages.extend(
            [
                {"type": "deliver_reply", "delivery_id": "buffer-me", "reply": {}},
                {"type": "rpc_response", "request_id": request_id, "ok": True, "payload": "bad-payload"},
            ]
        )
        with pytest.raises(RuntimeError, match="invalid payload"):
            await task

    asyncio.run(_rpc_failure())
    asyncio.run(_rpc_invalid_payload())
    assert any(item.get("type") == "deliver_reply" for item in context._buffered_control_messages)


def test_im_plugin_context_identity_and_type_validation_helpers():
    context = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data/plugin",
    )

    assert context._coerce_route(None) is None
    route = context._coerce_route({"target_type": "cocoon", "target_id": "c-1"})
    assert route == ImInboundRoute(target_type="cocoon", target_id="c-1", metadata_json={})
    assert context._coerce_route(route) is route

    assert context._coerce_delivery_result(None) == ImDeliveryResult(ok=True)
    assert context._coerce_delivery_result(True) == ImDeliveryResult(ok=True)
    assert context._coerce_delivery_result(False) == ImDeliveryResult(
        ok=False,
        error="Outbound reply handler reported failure",
    )
    assert context._coerce_delivery_result({"ok": True, "metadata_json": {"sent": True}}) == ImDeliveryResult(
        ok=True,
        error=None,
        retryable=True,
        metadata_json={"sent": True},
    )

    with pytest.raises(TypeError):
        context._coerce_route("bad")
    with pytest.raises(TypeError):
        context._coerce_delivery_result("bad")
    with pytest.raises(ValueError, match="Exactly one"):
        context._single_identity_payload(
            id_value=None,
            username_value=None,
            id_key="user_id",
            username_key="username",
            subject="user",
        )
    with pytest.raises(ValueError, match="Exactly one"):
        context._single_identity_payload(
            id_value="u-1",
            username_value="alice",
            id_key="user_id",
            username_key="username",
            subject="user",
        )
    assert context._single_identity_payload(
        id_value="u-1",
        username_value=None,
        id_key="user_id",
        username_key="username",
        subject="user",
    ) == {"user_id": "u-1"}
    assert context._single_identity_payload(
        id_value=None,
        username_value="alice",
        id_key="user_id",
        username_key="username",
        subject="user",
    ) == {"username": "alice"}


def test_im_plugin_context_create_chat_group_requires_single_owner_identity():
    context = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data/plugin",
    )

    async def _exercise():
        with pytest.raises(ValueError, match="Exactly one"):
            await context.create_chat_group(
                name="Room",
                owner_user_id="user-1",
                owner_username="alice",
                character_id="char-1",
                selected_model_id="model-1",
            )

    asyncio.run(_exercise())
