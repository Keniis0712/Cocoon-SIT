import asyncio

import app.services.plugins.sdk.im_sdk_runtime as im_sdk_module
from app.services.plugins.sdk.external_sdk import ExternalEventContext
from app.services.plugins.sdk.im_sdk import (
    ImDeliveryResult,
    ImInboundRoute,
    ImPluginContext,
    ImPrivateMessage,
)


class _Queue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)

    def get(self, block=True, timeout=None):
        if not self.items:
            raise __import__("queue").Empty()
        return self.items.pop(0)


def test_external_event_context_emits_events_and_heartbeats():
    queue = _Queue()
    context = ExternalEventContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        event_name="tick",
        plugin_config={"x": 1},
        event_config={"y": 2},
        data_dir="data/plugin",
        outbound_queue=queue,
    )

    context.emit_event({"summary": "wake"})
    context.heartbeat()
    context.report_user_error("user-1", "bad key")
    context.clear_user_error("user-1")

    assert queue.items[0] == {
        "type": "external_event",
        "plugin_event": "tick",
        "envelope": {"summary": "wake"},
    }
    assert queue.items[1]["type"] == "heartbeat"
    assert queue.items[2]["type"] == "user_error"
    assert queue.items[3]["type"] == "user_error_clear"


def test_sdk_contexts_noop_without_queues():
    external = ExternalEventContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        event_name="tick",
        plugin_config={},
        event_config={},
        data_dir="data/plugin",
        outbound_queue=None,
    )
    im = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data/plugin",
        inbound_queue=None,
        outbound_queue=None,
    )

    external.emit_event({"ignored": True})
    external.heartbeat()
    im.heartbeat()


def test_im_plugin_context_emits_heartbeat_and_inbound_messages():
    outbound = _Queue()
    context = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={"x": 1},
        data_dir="data/plugin",
        inbound_queue=_Queue(),
        outbound_queue=outbound,
    )

    context.heartbeat()
    context.report_user_error("user-2", "invalid location")
    context.clear_user_error("user-2")
    asyncio.run(
        context.emit_private_message(
            ImInboundRoute(target_type="cocoon", target_id="cocoon-1"),
            ImPrivateMessage(
                account_id="acct-1",
                conversation_id="conv-1",
                sender_id="sender-1",
                sender_display_name="Alice",
                text="hello",
                message_id="msg-1",
                occurred_at="2026-04-23T00:00:00+00:00",
            ),
        )
    )

    assert outbound.items[0]["type"] == "heartbeat"
    assert outbound.items[1]["type"] == "user_error"
    assert outbound.items[2]["type"] == "user_error_clear"
    assert outbound.items[3]["type"] == "im_inbound_message"
    assert outbound.items[3]["route"]["target_id"] == "cocoon-1"


def test_im_plugin_context_supports_callbacks_rpc_and_outbound_delivery():
    inbound = _Queue()
    outbound = _Queue()
    context = ImPluginContext(
        plugin_name="plugin",
        plugin_version="1.0.0",
        plugin_config={},
        data_dir="data/plugin",
        inbound_queue=inbound,
        outbound_queue=outbound,
    )

    @context.on_private_message
    async def _route_private(message):
        assert message.sender_display_name == "Alice"
        return ImInboundRoute(target_type="cocoon", target_id="cocoon-9")

    deliveries = []

    @context.on_outbound_reply
    async def _reply_handler(reply):
        deliveries.append(reply.reply_text)
        return ImDeliveryResult(ok=True)

    async def _exercise():
        route = await context.handle_private_message(
            ImPrivateMessage(
                account_id="acct-1",
                conversation_id="conv-1",
                sender_id="sender-1",
                sender_display_name="Alice",
                text="hello",
                message_id="msg-1",
                occurred_at="2026-04-23T00:00:00+00:00",
            )
        )
        assert route is not None and route.target_id == "cocoon-9"
        inbound.items.insert(
            0,
            {
                "type": "rpc_response",
                "request_id": "req-created",
                "ok": True,
                "payload": {"id": "created-cocoon"},
            },
        )
        inbound.items.insert(
            1,
            {
                "type": "rpc_response",
                "request_id": "req-binding",
                "ok": True,
                "payload": {"user_id": "user-1", "username": "alice"},
            },
        )
        inbound.items.insert(
            2,
            {
                "type": "rpc_response",
                "request_id": "req-targets",
                "ok": True,
                "payload": {
                    "items": [{"target_type": "cocoon", "target_id": "cocoon-1", "name": "Bridge"}]
                },
            },
        )
        inbound.items.insert(
            3,
            {
                "type": "rpc_response",
                "request_id": "req-characters",
                "ok": True,
                "payload": {"items": [{"character_id": "char-1", "name": "Bridge Character"}]},
            },
        )
        inbound.items.insert(
            4,
            {
                "type": "rpc_response",
                "request_id": "req-route-upsert",
                "ok": True,
                "payload": {"id": "route-1"},
            },
        )
        inbound.items.insert(
            5,
            {
                "type": "rpc_response",
                "request_id": "req-route-delete",
                "ok": True,
                "payload": {"deleted": True},
            },
        )
        original_uuid4 = im_sdk_module.uuid4
        request_ids = iter(
            (
                "req-created",
                "req-binding",
                "req-targets",
                "req-characters",
                "req-route-upsert",
                "req-route-delete",
            )
        )
        im_sdk_module.uuid4 = lambda: type("X", (), {"hex": next(request_ids)})()
        try:
            response = await context.create_cocoon(
                name="Bridge",
                owner_user_id="user-1",
                character_id="char-1",
                selected_model_id="model-1",
            )
            binding_response = await context.verify_user_binding(
                username="alice", token="secret-token"
            )
            targets_response = await context.list_accessible_targets(user_id="user-1")
            characters_response = await context.list_accessible_characters(user_id="user-1")
            route_response = await context.upsert_im_target_route(
                target_type="cocoon",
                target_id="cocoon-1",
                external_platform="onebot_v11",
                conversation_kind="private",
                external_account_id="acct-1",
                external_conversation_id="conv-1",
                metadata_json={"conversation_kind": "private"},
            )
            delete_response = await context.delete_im_target_route(
                external_platform="onebot_v11",
                conversation_kind="private",
                external_account_id="acct-1",
                external_conversation_id="conv-1",
            )
        finally:
            im_sdk_module.uuid4 = original_uuid4
        assert response["id"] == "created-cocoon"
        assert binding_response["user_id"] == "user-1"
        assert targets_response["items"][0]["target_id"] == "cocoon-1"
        assert characters_response["items"][0]["character_id"] == "char-1"
        assert route_response["id"] == "route-1"
        assert delete_response["deleted"] is True
        inbound.items.append(
            {
                "type": "deliver_reply",
                "delivery_id": "delivery-1",
                "reply": {
                    "delivery_id": "delivery-1",
                    "plugin_id": "plugin-1",
                    "target_type": "cocoon",
                    "target_id": "cocoon-9",
                    "reply_text": "pong",
                    "action_id": "action-1",
                    "message_id": "message-1",
                    "source_message_id": "msg-1",
                    "external_account_id": "acct-1",
                    "external_conversation_id": "conv-1",
                    "external_message_id": "msg-1",
                    "external_sender_id": "sender-1",
                    "external_sender_display_name": "Alice",
                    "metadata_json": {},
                },
            }
        )
        inbound.items.append({"type": "stop"})
        task = asyncio.create_task(context.run_forever(poll_interval_seconds=0.01))
        await task

    asyncio.run(_exercise())

    assert any(item["type"] == "im_inbound_message" for item in outbound.items)
    assert any(
        item["type"] == "rpc_request" and item["method"] == "create_cocoon"
        for item in outbound.items
    )
    assert any(
        item["type"] == "rpc_request" and item["method"] == "verify_user_binding"
        for item in outbound.items
    )
    assert any(
        item["type"] == "rpc_request" and item["method"] == "list_accessible_targets"
        for item in outbound.items
    )
    assert any(
        item["type"] == "rpc_request" and item["method"] == "list_accessible_characters"
        for item in outbound.items
    )
    assert any(
        item["type"] == "rpc_request" and item["method"] == "upsert_im_target_route"
        for item in outbound.items
    )
    assert any(
        item["type"] == "rpc_request" and item["method"] == "delete_im_target_route"
        for item in outbound.items
    )
    assert any(
        item["type"] == "delivery_result" and item["delivery_id"] == "delivery-1"
        for item in outbound.items
    )
    assert deliveries == ["pong"]
