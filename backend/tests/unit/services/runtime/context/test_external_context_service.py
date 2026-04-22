from types import SimpleNamespace

from app.models import Cocoon, CocoonTagBinding, MemoryChunk, Message, SessionState, TagRegistry
from app.services.runtime.context.external_context_service import ExternalContextService
from app.services.runtime.types import RuntimeEvent
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_external_context_service_handles_wakeup_and_missing_pull_inputs():
    session_factory = _session_factory()
    service = ExternalContextService(
        memory_service=SimpleNamespace(get_visible_memories=lambda **kwargs: []),
        message_window_service=SimpleNamespace(list_visible_messages=lambda *args, **kwargs: []),
    )

    with session_factory() as session:
        wakeup = service.build(
            session,
            RuntimeEvent(event_type="wakeup", cocoon_id="cocoon-1", chat_group_id=None, action_id="action-1", payload={"reason": "ping"}),
        )
        no_source = service.build(
            session,
            RuntimeEvent(event_type="pull", cocoon_id="cocoon-1", chat_group_id=None, action_id="action-1", payload={}),
        )
        missing_source = service.build(
            session,
            RuntimeEvent(
                event_type="merge",
                cocoon_id="cocoon-1",
                chat_group_id=None,
                action_id="action-1",
                payload={"source_cocoon_id": "missing"},
            ),
        )
        regular = service.build(
            session,
            RuntimeEvent(event_type="chat", cocoon_id="cocoon-1", chat_group_id=None, action_id="action-1", payload={}),
        )

        assert wakeup == {"wakeup_context": {"reason": "ping"}}
        assert no_source == {}
        assert missing_source == {}
        assert regular == {}


def test_external_context_service_builds_merge_context_and_filters_isolated_content():
    session_factory = _session_factory()
    message_calls = []
    memory_calls = []
    isolated_message = Message(id="m1", cocoon_id="source-1", role="user", content="hidden", tags_json=["isolated-id"])
    visible_message = Message(id="m2", cocoon_id="source-1", role="assistant", content="visible", tags_json=["shared-id"])
    isolated_memory = MemoryChunk(
        id="mem1",
        cocoon_id="source-1",
        owner_user_id="user-1",
        character_id="character-1",
        scope="session",
        content="hidden-memory",
        summary="hidden",
        tags_json=["isolated-id"],
    )
    visible_memory = MemoryChunk(
        id="mem2",
        cocoon_id="source-1",
        owner_user_id="user-1",
        character_id="character-1",
        scope="session",
        content="visible-memory",
        summary="visible",
        tags_json=["shared-id"],
    )
    service = ExternalContextService(
        memory_service=SimpleNamespace(
            get_visible_memories=lambda **kwargs: (memory_calls.append(kwargs) or [isolated_memory, visible_memory])
        ),
        message_window_service=SimpleNamespace(
            list_visible_messages=lambda *args, **kwargs: (message_calls.append((args, kwargs)) or [isolated_message, visible_message])
        ),
    )

    with session_factory() as session:
        source = Cocoon(
            id="source-1",
            name="Source",
            owner_user_id="user-1",
            character_id="character-1",
            selected_model_id="model-1",
            max_context_messages=7,
        )
        target = Cocoon(
            id="target-1",
            name="Target",
            owner_user_id="user-1",
            character_id="character-1",
            selected_model_id="model-1",
        )
        session.add_all(
            [
                source,
                target,
                SessionState(cocoon_id=source.id, relation_score=5, persona_json={"mood": "calm"}, active_tags_json=["shared-id"]),
                TagRegistry(id="isolated-id", tag_id="isolated", brief="iso", visibility="private", is_isolated=True, meta_json={}),
                TagRegistry(id="shared-id", tag_id="shared", brief="shared", visibility="shared", is_isolated=False, meta_json={}),
                CocoonTagBinding(cocoon_id=target.id, tag_id="shared-id"),
            ]
        )
        session.commit()

        result = service.build(
            session,
            RuntimeEvent(
                event_type="merge",
                cocoon_id=target.id,
                chat_group_id=None,
                action_id="action-1",
                payload={"source_cocoon_id": source.id},
            ),
        )

        assert result["source_cocoon"].id == source.id
        assert result["source_state"].relation_score == 5
        assert [message.id for message in result["source_messages"]] == ["m2"]
        assert [memory.id for memory in result["source_memories"]] == ["mem2"]
        assert result["merge_context"]["source_cocoon"] == {"id": source.id, "name": "Source"}
        assert result["merge_context"]["source_state"] == {
            "relation_score": 5,
            "persona_json": {"mood": "calm"},
            "active_tags_json": ["shared-id"],
        }
        assert result["merge_context"]["source_messages"] == [{"role": "assistant", "content": "visible"}]
        assert result["merge_context"]["source_memories"] == [
            {"scope": "session", "summary": "visible", "content": "visible-memory"}
        ]
        assert message_calls[0][0][1:] == (7, ["shared-id"])
        assert message_calls[0][1] == {"cocoon_id": source.id}
        assert memory_calls[0]["cocoon_id"] == source.id
        assert memory_calls[0]["query_text"] == source.id


def test_external_context_service_handles_missing_source_state_for_pull():
    session_factory = _session_factory()
    service = ExternalContextService(
        memory_service=SimpleNamespace(get_visible_memories=lambda **kwargs: []),
        message_window_service=SimpleNamespace(list_visible_messages=lambda *args, **kwargs: []),
    )

    with session_factory() as session:
        source = Cocoon(
            id="source-2",
            name="Source Two",
            owner_user_id="user-1",
            character_id="character-1",
            selected_model_id="model-1",
            max_context_messages=5,
        )
        target = Cocoon(
            id="target-2",
            name="Target Two",
            owner_user_id="user-1",
            character_id="character-1",
            selected_model_id="model-1",
        )
        session.add_all([source, target])
        session.commit()

        result = service.build(
            session,
            RuntimeEvent(
                event_type="pull",
                cocoon_id=target.id,
                chat_group_id=None,
                action_id="action-1",
                payload={"source_cocoon_id": source.id},
            ),
        )

        assert result["source_cocoon"].id == source.id
        assert result["source_state"] is None
        assert result["source_messages"] == []
        assert result["source_memories"] == []
