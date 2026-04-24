from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import ActionDispatch, Character, ChatGroupMember, ChatGroupRoom, Cocoon, Message, PluginDefinition, PluginImTargetRoute, User
from app.services.access.im_bind_token_service import ImBindTokenService
from app.services.plugins.manager import PluginRuntimeManager
from app.services.security.authorization_service import AuthorizationService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


class _RecordingDispatchService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def enqueue_chat_message(self, *args, **kwargs):
        self.calls.append(("cocoon", args, kwargs))
        return ActionDispatch(cocoon_id=args[1], event_type="chat", payload_json=dict(kwargs.get("extra_payload") or {}))

    def enqueue_chat_group_message(self, *args, **kwargs):
        self.calls.append(("chat_group", args, kwargs))
        return Message(chat_group_id=args[1], role="user", content=kwargs["content"])


def test_manager_lists_accessible_im_targets_for_bound_user():
    session_factory = _session_factory()
    manager = PluginRuntimeManager(
        session_factory=session_factory,
        settings=SimpleNamespace(plugin_watchdog_interval_seconds=1, plugin_short_lived_max_workers=1),
        external_wakeup_service=SimpleNamespace(),
        message_dispatch_service=SimpleNamespace(),
        im_bind_token_service=ImBindTokenService(),
    )

    with session_factory() as session:
        session.info["container"] = SimpleNamespace(authorization_service=AuthorizationService())
        owner = User(username="owner", password_hash="hash")
        member = User(username="member", password_hash="hash")
        stranger = User(username="stranger", password_hash="hash")
        session.add_all([owner, member, stranger])
        session.flush()

        visible_character = Character(name="visible", prompt_summary="", settings_json={}, created_by_user_id=member.id)
        hidden_character = Character(name="hidden", prompt_summary="", settings_json={}, created_by_user_id=stranger.id)
        session.add_all([visible_character, hidden_character])
        session.flush()

        visible_cocoon = Cocoon(
            name="Visible Cocoon",
            owner_user_id=member.id,
            character_id=visible_character.id,
            selected_model_id="model-1",
        )
        hidden_cocoon = Cocoon(
            name="Hidden Cocoon",
            owner_user_id=stranger.id,
            character_id=hidden_character.id,
            selected_model_id="model-1",
        )
        visible_room = ChatGroupRoom(
            name="Visible Room",
            owner_user_id=owner.id,
            character_id=visible_character.id,
            selected_model_id="model-1",
        )
        hidden_room = ChatGroupRoom(
            name="Hidden Room",
            owner_user_id=stranger.id,
            character_id=hidden_character.id,
            selected_model_id="model-1",
        )
        session.add_all([visible_cocoon, hidden_cocoon, visible_room, hidden_room])
        session.flush()
        session.add(ChatGroupMember(room_id=visible_room.id, user_id=member.id, member_role="member"))
        session.commit()

        response = manager._rpc_list_accessible_targets(session, {"user_id": member.id})

    item_pairs = {(item["target_type"], item["target_id"]) for item in response["items"]}
    assert ("cocoon", visible_cocoon.id) in item_pairs
    assert ("chat_group", visible_room.id) in item_pairs
    assert ("cocoon", hidden_cocoon.id) not in item_pairs
    assert ("chat_group", hidden_room.id) not in item_pairs


def test_manager_lists_accessible_characters_for_bound_user():
    session_factory = _session_factory()
    manager = PluginRuntimeManager(
        session_factory=session_factory,
        settings=SimpleNamespace(plugin_watchdog_interval_seconds=1, plugin_short_lived_max_workers=1),
        external_wakeup_service=SimpleNamespace(),
        message_dispatch_service=SimpleNamespace(),
        im_bind_token_service=ImBindTokenService(),
    )

    with session_factory() as session:
        session.info["container"] = SimpleNamespace(authorization_service=AuthorizationService())
        member = User(username="member-two", password_hash="hash")
        stranger = User(username="stranger-two", password_hash="hash")
        session.add_all([member, stranger])
        session.flush()

        visible_character = Character(name="Visible Character", prompt_summary="", settings_json={}, created_by_user_id=member.id)
        hidden_character = Character(name="Hidden Character", prompt_summary="", settings_json={}, created_by_user_id=stranger.id)
        session.add_all([visible_character, hidden_character])
        session.commit()

        response = manager._rpc_list_accessible_characters(session, {"user_id": member.id})

    character_ids = {item["character_id"] for item in response["items"]}
    assert visible_character.id in character_ids
    assert hidden_character.id not in character_ids


def test_manager_lists_accessible_targets_by_username():
    session_factory = _session_factory()
    manager = PluginRuntimeManager(
        session_factory=session_factory,
        settings=SimpleNamespace(plugin_watchdog_interval_seconds=1, plugin_short_lived_max_workers=1),
        external_wakeup_service=SimpleNamespace(),
        message_dispatch_service=SimpleNamespace(),
        im_bind_token_service=ImBindTokenService(),
    )

    with session_factory() as session:
        session.info["container"] = SimpleNamespace(authorization_service=AuthorizationService())
        member = User(username="member-name", password_hash="hash")
        session.add(member)
        session.flush()
        character = Character(name="Visible Character", prompt_summary="", settings_json={}, created_by_user_id=member.id)
        session.add(character)
        session.flush()
        visible_cocoon = Cocoon(
            name="Visible Cocoon",
            owner_user_id=member.id,
            character_id=character.id,
            selected_model_id="model-1",
        )
        session.add(visible_cocoon)
        session.commit()

        response = manager._rpc_list_accessible_targets(session, {"username": member.username})

    item_pairs = {(item["target_type"], item["target_id"]) for item in response["items"]}
    assert ("cocoon", visible_cocoon.id) in item_pairs


def test_manager_upserts_and_deletes_im_target_route():
    session_factory = _session_factory()
    manager = PluginRuntimeManager(
        session_factory=session_factory,
        settings=SimpleNamespace(plugin_watchdog_interval_seconds=1, plugin_short_lived_max_workers=1),
        external_wakeup_service=SimpleNamespace(),
        message_dispatch_service=SimpleNamespace(),
        im_bind_token_service=ImBindTokenService(),
    )

    with session_factory() as session:
        plugin = PluginDefinition(
            name="bridge",
            display_name="Bridge",
            plugin_type="im",
            entry_module="main",
            service_function_name="run",
            status="enabled",
            data_dir="data/plugins/bridge",
        )
        owner = User(username="owner-route", password_hash="hash")
        character = Character(name="Visible Character", prompt_summary="", settings_json={}, created_by_user_id="seed")
        session.add_all([plugin, owner, character])
        session.flush()
        character.created_by_user_id = owner.id
        cocoon = Cocoon(
            name="Visible Cocoon",
            owner_user_id=owner.id,
            character_id=character.id,
            selected_model_id="model-1",
        )
        session.add(cocoon)
        session.commit()

        response = manager._rpc_upsert_im_target_route(
            session,
            plugin,
            {
                "target_type": "cocoon",
                "target_id": cocoon.id,
                "external_platform": "onebot_v11",
                "conversation_kind": "private",
                "external_account_id": "acct-1",
                "external_conversation_id": "conv-1",
                "metadata_json": {"conversation_kind": "private"},
            },
        )
        session.commit()

        route = session.scalar(select(PluginImTargetRoute))
        assert route is not None
        assert response["id"] == route.id
        assert route.target_id == cocoon.id

        delete_response = manager._rpc_delete_im_target_route(
            session,
            plugin,
            {
                "external_platform": "onebot_v11",
                "conversation_kind": "private",
                "external_account_id": "acct-1",
                "external_conversation_id": "conv-1",
            },
        )
        session.commit()

        assert delete_response["deleted"] is True
        assert session.scalar(select(PluginImTargetRoute)) is None


def test_manager_ingests_im_message_with_plugin_supplied_user_ids():
    session_factory = _session_factory()
    dispatch_service = _RecordingDispatchService()
    manager = PluginRuntimeManager(
        session_factory=session_factory,
        settings=SimpleNamespace(plugin_watchdog_interval_seconds=1, plugin_short_lived_max_workers=1),
        external_wakeup_service=SimpleNamespace(),
        message_dispatch_service=dispatch_service,
        im_bind_token_service=ImBindTokenService(),
    )

    with session_factory() as session:
        plugin = PluginDefinition(
            name="bridge",
            display_name="Bridge",
            plugin_type="im",
            entry_module="main",
            service_function_name="run",
            status="enabled",
            data_dir="data/plugins/bridge",
        )
        user = User(id="user-1", username="member", password_hash="hash")
        session.add_all([plugin, user])
        session.commit()

        manager._ingest_im_inbound_message(
            session,
            plugin=plugin,
            payload={
                "message_kind": "private",
                "route": {"target_type": "cocoon", "target_id": "cocoon-1", "metadata_json": {"platform": "onebot"}},
                "message": {
                    "account_id": "bot-1",
                    "conversation_id": "peer-1",
                    "sender_id": "peer-1",
                    "sender_display_name": "ken",
                    "sender_user_id": "user-1",
                    "owner_user_id": "user-1",
                    "memory_owner_user_id": "user-1",
                    "text": "hello from im",
                    "message_id": "msg-1",
                    "occurred_at": "2026-04-24T08:20:18+00:00",
                    "raw_payload": {"raw_message": "hello from im"},
                    "metadata_json": {"platform": "onebot"},
                },
            },
        )

    assert len(dispatch_service.calls) == 1
    kind, _, kwargs = dispatch_service.calls[0]
    assert kind == "cocoon"
    assert kwargs["sender_user_id"] == "user-1"
    assert kwargs["extra_payload"]["sender_user_id"] == "user-1"
    assert kwargs["extra_payload"]["owner_user_id"] == "user-1"
    assert kwargs["extra_payload"]["memory_owner_user_id"] == "user-1"


def test_manager_rejects_unknown_plugin_supplied_user_ids():
    session_factory = _session_factory()
    dispatch_service = _RecordingDispatchService()
    manager = PluginRuntimeManager(
        session_factory=session_factory,
        settings=SimpleNamespace(plugin_watchdog_interval_seconds=1, plugin_short_lived_max_workers=1),
        external_wakeup_service=SimpleNamespace(),
        message_dispatch_service=dispatch_service,
        im_bind_token_service=ImBindTokenService(),
    )

    with session_factory() as session:
        plugin = PluginDefinition(
            name="bridge",
            display_name="Bridge",
            plugin_type="im",
            entry_module="main",
            service_function_name="run",
            status="enabled",
            data_dir="data/plugins/bridge",
        )
        session.add(plugin)
        session.commit()

        with pytest.raises(ValueError, match="sender_user_id must reference an existing user"):
            manager._ingest_im_inbound_message(
                session,
                plugin=plugin,
                payload={
                    "message_kind": "private",
                    "route": {"target_type": "cocoon", "target_id": "cocoon-1", "metadata_json": {}},
                    "message": {
                        "account_id": "bot-1",
                        "conversation_id": "peer-1",
                        "sender_user_id": "missing-user",
                        "text": "hello from im",
                        "message_id": "msg-1",
                    },
                },
            )
