import asyncio
import sys
from pathlib import Path


PLUGIN_ROOT = Path.cwd() / "plugins" / "im" / "nonebot_onebot_v11_bridge"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from nbbridge.bridge import NoneBotOneBotBridge  # noqa: E402


class _FakeContext:
    def __init__(self, data_dir: Path) -> None:
        self.plugin_config = {
            "default_owner_username": "admin",
            "default_model_id": "model-1",
            "im_owner_id": "op-1",
        }
        self.data_dir = str(data_dir)
        self.created = []
        self.route_upserts = []
        self.route_deletes = []
        self.emitted_private = []
        self.emitted_group = []

    async def list_accessible_targets(self, *, user_id: str | None = None, username: str | None = None) -> dict:
        del user_id, username
        return {
            "items": [
                {
                    "target_type": "chat_group",
                    "target_id": "group-1",
                    "name": "Group Alpha",
                    "created_at": "2026-04-24T07:00:00+00:00",
                },
                {
                    "target_type": "cocoon",
                    "target_id": "cocoon-1",
                    "name": "Alpha",
                    "created_at": "2026-04-24T06:00:00+00:00",
                },
                {
                    "target_type": "cocoon",
                    "target_id": "cocoon-2",
                    "name": "Beta",
                    "created_at": "2026-04-24T05:00:00+00:00",
                },
            ]
        }

    async def list_accessible_characters(self, *, user_id: str | None = None, username: str | None = None) -> dict:
        del user_id, username
        return {
            "items": [
                {
                    "character_id": f"char-{index:02d}",
                    "name": f"Character {index:02d}",
                    "created_at": f"2026-04-24T{index:02d}:00:00+00:00",
                }
                for index in range(12, 0, -1)
            ]
        }

    async def create_cocoon(self, **kwargs) -> dict:
        self.created.append(kwargs)
        return {"id": "cocoon-new", "name": kwargs["name"]}

    async def create_chat_group(self, **kwargs) -> dict:
        self.created.append(kwargs)
        return {"id": "group-new", "name": kwargs["name"]}

    async def verify_user_binding(self, *, username: str, token: str) -> dict:
        return {"user_id": f"user-{username}", "username": username, "token": token}

    async def upsert_im_target_route(self, **kwargs) -> dict:
        self.route_upserts.append(kwargs)
        return {"id": "route-1", **kwargs}

    async def delete_im_target_route(self, **kwargs) -> dict:
        self.route_deletes.append(kwargs)
        return {"deleted": True}

    async def emit_private_message(self, route, message) -> None:
        self.emitted_private.append((route, message))

    async def emit_group_message(self, route, message) -> None:
        self.emitted_group.append((route, message))


def _private_payload(*, sender_id: str = "user-qq", text: str = "hello") -> dict:
    return {
        "message_kind": "private",
        "account_id": "bot-1",
        "conversation_id": sender_id,
        "sender_display_name": "Alice",
        "sender_id": sender_id,
        "text": text,
    }


def _group_payload(*, text: str = "hello", sender_id: str = "member-qq") -> dict:
    return {
        "message_kind": "group",
        "account_id": "bot-1",
        "conversation_id": "im-group-1",
        "group_name": "IM Group",
        "sender_display_name": "Bob",
        "sender_id": sender_id,
        "text": text,
        "message_id": "group-msg-1",
        "occurred_at": "2026-04-24T08:20:18+00:00",
        "raw_payload": {"raw_message": text},
        "metadata_json": {"platform": "nonebot_onebot_v11", "conversation_kind": "group"},
    }


def _build_bridge(tmp_path: Path) -> tuple[_FakeContext, NoneBotOneBotBridge]:
    ctx = _FakeContext(tmp_path)
    bridge = NoneBotOneBotBridge(ctx)
    bridge.route_store._save = lambda: None
    return ctx, bridge


def test_help_hides_op_for_non_op(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._handle_command(_private_payload(text="/help")))

    assert "/op" not in output
    assert "/attach" in output


def test_help_includes_op_for_owner(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._handle_command(_private_payload(sender_id="op-1", text="/help")))

    assert "/op group enable <im_group_id>" in output
    assert "/op role add <im_uid>" in output


def test_non_op_cannot_see_op_command_usage(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(
        bridge._handle_command(_private_payload(text="/op group enable im-group-1"))
    )

    assert output == "Unknown command. Use /help."


def test_create_requires_explicit_target_type(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._command_create(_private_payload(), ["Example", "Character 03"]))

    assert output == "Usage: /create <cocoon|group> [name] [character_name]"
    assert ctx.created == []


def test_create_cocoon_uses_explicit_type(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)

    output = asyncio.run(
        bridge._command_create(_private_payload(), ["cocoon", "Example", "Character 03"])
    )

    assert output == "Created cocoon: Example"
    assert ctx.created[0]["name"] == "Example"
    assert ctx.created[0]["character_id"] == "char-03"


def test_enable_stores_group_state_without_route(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = bridge._command_op_group_enable(_private_payload(sender_id="op-1"), ["im-group-1"])
    state = bridge.route_store.get_group_state("bot-1", "im-group-1")

    assert output == "Enabled IM group: im-group-1"
    assert state is not None
    assert state["enabled"] is True
    assert state["attached"] is False
    assert state["route"] is None


def test_group_attach_requires_enabled_state(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(
        bridge._command_op_group_attach(
            _private_payload(sender_id="op-1"),
            ["im-group-1", "group-1"],
        )
    )

    assert output == "IM group is not enabled. Use /op group enable first."


def test_group_attach_creates_backend_route(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)
    bridge._command_op_group_enable(_private_payload(sender_id="op-1"), ["im-group-1"])

    output = asyncio.run(
        bridge._command_op_group_attach(
            _private_payload(sender_id="op-1"),
            ["im-group-1", "group-1"],
        )
    )
    state = bridge.route_store.get_group_state("bot-1", "im-group-1")

    assert output == "Attached IM group im-group-1 to chat_group Group Alpha"
    assert state is not None
    assert state["enabled"] is True
    assert state["attached"] is True
    assert state["route"]["target_id"] == "group-1"
    assert ctx.route_upserts[0]["conversation_kind"] == "group"


def test_group_detach_keeps_group_enabled(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)
    bridge._command_op_group_enable(_private_payload(sender_id="op-1"), ["im-group-1"])
    asyncio.run(
        bridge._command_op_group_attach(
            _private_payload(sender_id="op-1"),
            ["im-group-1", "group-1"],
        )
    )

    output = asyncio.run(
        bridge._command_op_group_detach(_private_payload(sender_id="op-1"), ["im-group-1"])
    )
    state = bridge.route_store.get_group_state("bot-1", "im-group-1")

    assert output == "Detached IM group: im-group-1"
    assert state is not None
    assert state["enabled"] is True
    assert state["attached"] is False
    assert ctx.route_deletes[0]["conversation_kind"] == "group"


def test_group_disable_clears_route_and_disables(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)
    bridge._command_op_group_enable(_private_payload(sender_id="op-1"), ["im-group-1"])
    asyncio.run(
        bridge._command_op_group_attach(
            _private_payload(sender_id="op-1"),
            ["im-group-1", "group-1"],
        )
    )

    output = asyncio.run(
        bridge._command_op_group_disable(_private_payload(sender_id="op-1"), ["im-group-1"])
    )
    state = bridge.route_store.get_group_state("bot-1", "im-group-1")

    assert output == "Disabled IM group: im-group-1"
    assert state is not None
    assert state["enabled"] is False
    assert state["attached"] is False
    assert ctx.route_deletes[0]["external_conversation_id"] == "im-group-1"


def test_im_owner_id_cannot_be_removed_from_ops(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = bridge._command_op_role_remove(_private_payload(sender_id="op-1"), ["op-1"])

    assert output == "Cannot remove the configured im_owner_id from OP access."


def test_group_messages_do_not_execute_commands_even_when_attached(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)
    bridge._command_op_group_enable(_private_payload(sender_id="op-1"), ["im-group-1"])
    asyncio.run(
        bridge._command_op_group_attach(
            _private_payload(sender_id="op-1"),
            ["im-group-1", "group-1"],
        )
    )

    command_response = asyncio.run(bridge._handle_command(_group_payload(text="/help")))
    asyncio.run(bridge._dispatch_inbound_event(_group_payload(text="/help")))

    assert command_response == ""
    assert len(ctx.emitted_group) == 1
    assert ctx.emitted_group[0][1].text == "/help"


def test_disabled_group_messages_are_dropped(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)

    asyncio.run(bridge._dispatch_inbound_event(_group_payload()))

    assert ctx.emitted_group == []


def test_enabled_but_unattached_group_messages_are_dropped(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)
    bridge._command_op_group_enable(_private_payload(sender_id="op-1"), ["im-group-1"])

    asyncio.run(bridge._dispatch_inbound_event(_group_payload()))

    assert ctx.emitted_group == []


def test_attached_group_message_uses_external_identity_only(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)
    bridge._command_op_group_enable(_private_payload(sender_id="op-1"), ["im-group-1"])
    asyncio.run(
        bridge._command_op_group_attach(
            _private_payload(sender_id="op-1"),
            ["im-group-1", "group-1"],
        )
    )

    asyncio.run(bridge._dispatch_inbound_event(_group_payload()))

    assert len(ctx.emitted_group) == 1
    _, message = ctx.emitted_group[0]
    assert message.sender_user_id is None
    assert message.owner_user_id is None
    assert message.memory_owner_user_id is None
    assert message.sender_id == "member-qq"
    assert message.sender_display_name == "Bob"


def test_private_binding_still_dispatches_bound_identity(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)
    bridge.route_store.save_binding(
        "private",
        "bot-1",
        "user-qq",
        route={
            "target_type": "cocoon",
            "target_id": "cocoon-1",
            "metadata_json": {"platform": "nonebot_onebot_v11", "conversation_kind": "private"},
        },
        attached=True,
        tags=[],
    )
    bridge.route_store.save_platform_binding(
        "bot-1",
        "user-qq",
        platform_user_id="user-1",
        platform_username="admin",
    )

    asyncio.run(
        bridge._dispatch_inbound_event(
            {
                **_private_payload(),
                "text": "hello",
                "message_id": "msg-1",
                "occurred_at": "2026-04-24T08:20:18+00:00",
                "raw_payload": {"raw_message": "hello"},
                "metadata_json": {"platform": "nonebot_onebot_v11"},
            }
        )
    )

    assert len(ctx.emitted_private) == 1
    _, message = ctx.emitted_private[0]
    assert message.sender_user_id == "user-1"
    assert message.owner_user_id == "user-1"
    assert message.memory_owner_user_id == "user-1"
