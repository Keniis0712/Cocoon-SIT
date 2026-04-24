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
        }
        self.data_dir = str(data_dir)
        self.created = []
        self.route_upserts = []
        self.route_deletes = []
        self.emitted_private = []
        self.emitted_group = []

    async def list_accessible_targets(self, *, user_id: str | None = None, username: str | None = None) -> dict:
        return {
            "items": [
                {"target_type": "cocoon", "target_id": "cocoon-1", "name": "Alpha", "created_at": "2026-04-24T06:00:00+00:00"},
                {"target_type": "cocoon", "target_id": "cocoon-2", "name": "Beta", "created_at": "2026-04-24T05:00:00+00:00"},
            ]
        }

    async def list_accessible_characters(self, *, user_id: str | None = None, username: str | None = None) -> dict:
        return {
            "items": [
                {"character_id": f"char-{index:02d}", "name": f"Character {index:02d}", "created_at": f"2026-04-24T{index:02d}:00:00+00:00"}
                for index in range(12, 0, -1)
            ]
        }

    async def create_cocoon(self, **kwargs) -> dict:
        self.created.append(kwargs)
        return {"id": "cocoon-new", "name": kwargs["name"]}

    async def create_chat_group(self, **kwargs) -> dict:
        self.created.append(kwargs)
        return {"id": "group-new", "name": kwargs["name"]}

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


class _FakeMixedTargetContext(_FakeContext):
    async def list_accessible_targets(self, *, user_id: str | None = None, username: str | None = None) -> dict:
        return {
            "items": [
                {"target_type": "chat_group", "target_id": "group-1", "name": "Group Alpha", "created_at": "2026-04-24T07:00:00+00:00"},
                {"target_type": "cocoon", "target_id": "cocoon-1", "name": "Alpha", "created_at": "2026-04-24T06:00:00+00:00"},
            ]
        }


def _private_payload() -> dict:
    return {
        "message_kind": "private",
        "account_id": "bot-1",
        "conversation_id": "user-qq",
        "sender_display_name": "Alice",
        "sender_id": "user-qq",
    }


def _build_bridge(tmp_path: Path, ctx: _FakeContext | None = None) -> tuple[_FakeContext, NoneBotOneBotBridge]:
    current_ctx = ctx or _FakeContext(tmp_path)
    bridge = NoneBotOneBotBridge(current_ctx)
    bridge.route_store._save = lambda: None
    return current_ctx, bridge


def test_bridge_lists_characters_with_pagination(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._command_list(_private_payload(), ["characters", "2"]))

    assert "characters 第 2/2 页，共 12 项" in output
    assert "11. - Character 02" in output
    assert "12. - Character 01" in output
    assert "char-02" not in output
    assert "char-01" not in output


def test_bridge_create_uses_character_name(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._command_create(_private_payload(), ["测试会话", "Character 03"]))

    assert "cocoon" in output
    assert "cocoon-new" not in output
    assert ctx.created[0]["name"] == "测试会话"
    assert ctx.created[0]["character_id"] == "char-03"
    assert ctx.created[0]["owner_username"] == "admin"


def test_bridge_create_requires_character_name_when_multiple_exist(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._command_create(_private_payload(), ["测试会话"]))

    assert output == "请先执行 /list characters，然后使用 /create [名称] [character_name]。"
    assert ctx.created == []


def test_bridge_lists_cocoons_without_showing_target_ids(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._command_list(_private_payload(), ["cocoons"]))

    assert "1. - Alpha" in output
    assert "2. - Beta" in output
    assert "cocoon-1" not in output
    assert "cocoon-2" not in output


def test_bridge_attach_supports_id_mode_for_private_chat(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._command_attach(_private_payload(), ["id", "cocoon-1"]))
    binding = bridge.route_store.get_binding("private", "bot-1", "user-qq")

    assert output == "已附着到 cocoon：Alpha"
    assert binding is not None
    assert binding["route"]["target_type"] == "cocoon"
    assert binding["route"]["target_id"] == "cocoon-1"
    assert bridge.ctx.route_upserts[0]["target_id"] == "cocoon-1"


def test_bridge_attach_supports_name_mode_for_private_chat(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._command_attach(_private_payload(), ["name", "Alpha"]))
    binding = bridge.route_store.get_binding("private", "bot-1", "user-qq")

    assert output == "已附着到 cocoon：Alpha"
    assert binding is not None
    assert binding["route"]["target_id"] == "cocoon-1"
    assert bridge.ctx.route_upserts[0]["external_conversation_id"] == "user-qq"


def test_bridge_private_chat_rejects_chat_group_attach_by_name(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path, _FakeMixedTargetContext(tmp_path))

    output = asyncio.run(bridge._command_attach(_private_payload(), ["name", "Group Alpha"]))
    binding = bridge.route_store.get_binding("private", "bot-1", "user-qq")

    assert output == "找不到目标；先用 /list 查看，然后使用 /attach id <id> 或 /attach name <name>。"
    assert binding is None


def test_bridge_attach_rejects_unknown_explicit_target_id(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._command_attach(_private_payload(), ["id", "cocoon:1"]))
    binding = bridge.route_store.get_binding("private", "bot-1", "user-qq")

    assert output == "找不到目标；先用 /list 查看，然后使用 /attach id <id> 或 /attach name <name>。"
    assert binding is None


def test_bridge_attach_requires_supported_mode(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    output = asyncio.run(bridge._command_attach(_private_payload(), ["1"]))
    binding = bridge.route_store.get_binding("private", "bot-1", "user-qq")

    assert output == "用法：/attach id <id> 或 /attach name <name>。"
    assert binding is None


def test_bridge_detach_deletes_backend_route(tmp_path: Path):
    ctx, bridge = _build_bridge(tmp_path)
    asyncio.run(bridge._command_attach(_private_payload(), ["id", "cocoon-1"]))

    output = asyncio.run(bridge._command_detach(_private_payload()))
    binding = bridge.route_store.get_binding("private", "bot-1", "user-qq")

    assert output == "已解除附着。"
    assert binding is not None
    assert binding["attached"] is False
    assert ctx.route_deletes[0]["conversation_kind"] == "private"
    assert ctx.route_deletes[0]["external_conversation_id"] == "user-qq"


def test_bridge_dispatches_private_identity_from_platform_binding(tmp_path: Path):
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


def test_bridge_compacts_onebot_payload(tmp_path: Path):
    _, bridge = _build_bridge(tmp_path)

    compact = bridge._compact_onebot_payload(
        {
            "post_type": "message",
            "message_type": "private",
            "raw_message": "3分钟之后提醒我，好吗？",
            "message": [{"type": "text", "data": {"text": "3分钟之后提醒我，好吗？", "extra": "drop"}}],
            "sender": {"nickname": "ken", "card": "", "role": "drop"},
            "raw": {
                "msgId": "7632237708335169710",
                "msgSeq": "70",
                "peerUin": "399384532",
                "elements": [
                    {
                        "textElement": {
                            "content": "3分钟之后提醒我，好吗？",
                            "needNotify": 0,
                        }
                    }
                ],
                "emojiLikesList": [{"x": 1}],
            },
        }
    )

    assert compact["post_type"] == "message"
    assert compact["message"][0] == {"type": "text", "data": {"text": "3分钟之后提醒我，好吗？"}}
    assert compact["sender"] == {"nickname": "ken"}
    assert compact["raw"]["msgId"] == "7632237708335169710"
    assert compact["raw"]["text_fragments"] == ["3分钟之后提醒我，好吗？"]
    assert "emojiLikesList" not in compact["raw"]
