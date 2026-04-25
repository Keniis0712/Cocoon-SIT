from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.models import Character, ChatGroupRoom, Cocoon, SessionState, TagRegistry
from app.services.runtime.context.builder import ContextBuilder
from app.services.runtime.types import RuntimeEvent
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def _event(
    *,
    event_type: str = "chat",
    cocoon_id: str | None = "cocoon-1",
    chat_group_id: str | None = None,
    payload: dict | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=event_type,
        cocoon_id=cocoon_id,
        chat_group_id=chat_group_id,
        action_id="action-1",
        payload=payload or {},
    )


def test_context_builder_builds_chat_group_context_with_tags_and_pending_wakeups(monkeypatch):
    session_factory = _session_factory()
    visible_messages = [
        SimpleNamespace(role="assistant", sender_user_id=None, content="ignored", is_retracted=False),
        SimpleNamespace(role="user", sender_user_id="member-1", content="hello there", is_retracted=True),
        SimpleNamespace(role="user", sender_user_id="member-2", content="latest question", is_retracted=False),
    ]
    memory_hit = SimpleNamespace(
        memory=SimpleNamespace(id="memory-1", summary="remembered"),
        to_artifact_payload=lambda: {"id": "memory-1"},
    )
    wakeup_task = SimpleNamespace(
        id="wake-1",
        run_at=datetime(2026, 4, 21, 12, 0, 0),
        reason="follow up",
        status="queued",
        cancelled_at=None,
        superseded_by_task_id=None,
        payload_json={"kind": "unit"},
    )
    memory_calls = []
    window_calls = []
    external_calls = []

    builder = ContextBuilder(
        memory_service=SimpleNamespace(
            retrieve_visible_memories=lambda **kwargs: (memory_calls.append(kwargs) or [memory_hit])
        ),
        message_window_service=SimpleNamespace(
            list_visible_messages=lambda *args, **kwargs: (window_calls.append((args, kwargs)) or visible_messages)
        ),
        external_context_service=SimpleNamespace(
            build=lambda session, event: (external_calls.append((session, event)) or {"external": True})
        ),
    )
    monkeypatch.setattr(
        "app.services.runtime.context.builder.list_pending_wakeup_tasks",
        lambda session, cocoon_id=None, chat_group_id=None: [wakeup_task],
    )

    with session_factory() as session:
        character = Character(
            id="character-1",
            name="Guide",
            prompt_summary="",
            settings_json={},
            created_by_user_id="owner-1",
        )
        room = ChatGroupRoom(
            id="room-1",
            name="Room",
            owner_user_id="owner-1",
            character_id=character.id,
            selected_model_id="model-1",
            max_context_messages=8,
        )
        tag = TagRegistry(
            id="tag-row-1",
            tag_id="focus",
            brief="Keep focus",
            visibility="shared",
            is_isolated=True,
            meta_json={"weight": 2},
        )
        session.add_all(
            [
                character,
                room,
                SessionState(chat_group_id=room.id, persona_json={}, active_tags_json=["focus"]),
                tag,
            ]
        )
        session.commit()

        result = builder.build(
            session,
            _event(chat_group_id=room.id, cocoon_id=None, payload={"sender_user_id": 42}),
        )

    assert result.conversation.id == "room-1"
    assert result.character.id == "character-1"
    assert result.memory_context == [memory_hit.memory]
    assert result.memory_owner_user_id == "42"
    assert result.external_context["external"] is True
    assert result.external_context["pending_wakeups"] == [
        {
            "id": "wake-1",
            "run_at": "2026-04-21T12:00:00",
            "reason": "follow up",
            "status": "queued",
            "cancelled_at": None,
            "superseded_by_task_id": None,
            "payload_json": {"kind": "unit"},
        }
    ]
    assert "now_utc" not in result.external_context
    assert result.external_context["tag_catalog_by_ref"]["tag-row-1"]["brief"] == "Keep focus"
    assert result.external_context["tag_catalog_by_ref"]["focus"]["is_isolated"] is True
    assert window_calls[0][0][1:] == (8, ["focus"])
    assert window_calls[0][1] == {"cocoon_id": None, "chat_group_id": "room-1"}
    assert memory_calls[0]["owner_user_id"] == "42"
    assert memory_calls[0]["character_id"] == "character-1"
    assert memory_calls[0]["query_text"] == "latest question"
    assert memory_calls[0]["limit"] == 5
    assert external_calls and external_calls[0][1].chat_group_id == "room-1"


def test_context_builder_limits_cocoon_memory_lookup_to_current_cocoon(monkeypatch):
    session_factory = _session_factory()
    memory_calls = []
    builder = ContextBuilder(
        memory_service=SimpleNamespace(
            retrieve_visible_memories=lambda **kwargs: (memory_calls.append(kwargs) or [])
        ),
        message_window_service=SimpleNamespace(
            list_visible_messages=lambda *args, **kwargs: [
                SimpleNamespace(role="user", sender_user_id="owner-1", content="hi", is_retracted=False)
            ]
        ),
        external_context_service=SimpleNamespace(build=lambda session, event: {}),
    )
    monkeypatch.setattr(
        "app.services.runtime.context.builder.list_pending_wakeup_tasks",
        lambda session, cocoon_id=None, chat_group_id=None: [],
    )

    with session_factory() as session:
        character = Character(
            id="character-1",
            name="Guide",
            prompt_summary="",
            settings_json={},
            created_by_user_id="owner-1",
        )
        cocoon = Cocoon(
            id="cocoon-1",
            name="Solo",
            owner_user_id="owner-1",
            character_id=character.id,
            selected_model_id="model-1",
            max_context_messages=6,
        )
        session.add_all([character, cocoon])
        session.commit()

        result = builder.build(session, _event(cocoon_id=cocoon.id))

    assert result.memory_owner_user_id == "owner-1"
    assert memory_calls[0]["cocoon_id"] == "cocoon-1"
    assert memory_calls[0]["owner_user_id"] is None
    assert memory_calls[0]["character_id"] is None


def test_context_builder_build_raises_when_character_missing():
    session_factory = _session_factory()
    builder = ContextBuilder(
        memory_service=SimpleNamespace(retrieve_visible_memories=lambda **kwargs: []),
        message_window_service=SimpleNamespace(list_visible_messages=lambda *args, **kwargs: []),
        external_context_service=SimpleNamespace(build=lambda session, event: {}),
    )

    with session_factory() as session:
        session.add(
            Cocoon(
                id="cocoon-1",
                name="Solo",
                owner_user_id="owner-1",
                character_id="missing-character",
                selected_model_id="model-1",
            )
        )
        session.commit()

        with pytest.raises(ValueError, match="Character not found: missing-character"):
            builder.build(session, _event())


def test_context_builder_resolve_conversation_rejects_missing_targets():
    session_factory = _session_factory()
    builder = ContextBuilder(
        memory_service=SimpleNamespace(retrieve_visible_memories=lambda **kwargs: []),
        message_window_service=SimpleNamespace(list_visible_messages=lambda *args, **kwargs: []),
        external_context_service=SimpleNamespace(build=lambda session, event: {}),
    )

    with session_factory() as session:
        with pytest.raises(ValueError, match="Chat group room not found: room-missing"):
            builder._resolve_conversation(
                session,
                _event(chat_group_id="room-missing", cocoon_id=None),
            )
        with pytest.raises(ValueError, match="Cocoon not found: cocoon-missing"):
            builder._resolve_conversation(
                session,
                _event(cocoon_id="cocoon-missing"),
            )


def test_context_builder_resolves_memory_owner_from_payload_messages_and_owner():
    builder = ContextBuilder(
        memory_service=SimpleNamespace(retrieve_visible_memories=lambda **kwargs: []),
        message_window_service=SimpleNamespace(list_visible_messages=lambda *args, **kwargs: []),
        external_context_service=SimpleNamespace(build=lambda session, event: {}),
    )
    chat_group_conversation = SimpleNamespace(owner_user_id="owner-1")
    visible_messages = [
        SimpleNamespace(role="assistant", sender_user_id=None),
        SimpleNamespace(role="user", sender_user_id="member-9"),
    ]

    assert (
        builder._resolve_memory_owner_user_id(
            _event(cocoon_id="cocoon-1", payload={"memory_owner_user_id": "plugin-owner"}),
            SimpleNamespace(owner_user_id="cocoon-owner"),
            [],
        )
        == "plugin-owner"
    )
    assert (
        builder._resolve_memory_owner_user_id(
            _event(cocoon_id="cocoon-1", payload={"sender_user_id": "plugin-sender"}),
            SimpleNamespace(owner_user_id="cocoon-owner"),
            [],
        )
        == "plugin-sender"
    )
    assert (
        builder._resolve_memory_owner_user_id(
            _event(cocoon_id="cocoon-1"),
            SimpleNamespace(owner_user_id="cocoon-owner"),
            [],
        )
        == "cocoon-owner"
    )
    assert (
        builder._resolve_memory_owner_user_id(
            _event(chat_group_id="room-1", cocoon_id=None, payload={"sender_user_id": 99}),
            chat_group_conversation,
            visible_messages,
        )
        == "99"
    )
    assert (
        builder._resolve_memory_owner_user_id(
            _event(chat_group_id="room-1", cocoon_id=None, payload={"memory_owner_user_id": "fallback-user"}),
            chat_group_conversation,
            visible_messages,
        )
        == "fallback-user"
    )
    assert (
        builder._resolve_memory_owner_user_id(
            _event(chat_group_id="room-1", cocoon_id=None),
            chat_group_conversation,
            visible_messages,
        )
        == "member-9"
    )
    assert (
        builder._resolve_memory_owner_user_id(
            _event(chat_group_id="room-1", cocoon_id=None),
            chat_group_conversation,
            [SimpleNamespace(role="assistant", sender_user_id=None)],
        )
        == "owner-1"
    )


def test_context_builder_resolves_query_text_for_pull_merge_wakeup_and_default():
    builder = ContextBuilder(
        memory_service=SimpleNamespace(retrieve_visible_memories=lambda **kwargs: []),
        message_window_service=SimpleNamespace(list_visible_messages=lambda *args, **kwargs: []),
        external_context_service=SimpleNamespace(build=lambda session, event: {}),
    )
    chat_messages = [
        SimpleNamespace(role="user", content="old", is_retracted=False),
        SimpleNamespace(role="user", content="hidden", is_retracted=True),
    ]

    assert builder._resolve_query_text(_event(event_type="chat"), chat_messages) == "old"
    assert (
        builder._resolve_query_text(
            _event(event_type="pull", payload={"source_cocoon_id": "source-1"}),
            [],
        )
        == "pull:source-1"
    )
    assert (
        builder._resolve_query_text(
            _event(event_type="merge", payload={"source_cocoon_id": "source-2"}),
            [],
        )
        == "merge:source-2"
    )
    assert builder._resolve_query_text(_event(event_type="wakeup", payload={}), []) == "scheduled wakeup"
    assert builder._resolve_query_text(_event(event_type="system"), []) is None
