from __future__ import annotations

from types import SimpleNamespace

from app.models import ActionDispatch, Character, Cocoon, SessionState, User
from app.services.runtime.orchestration.side_effects import SideEffects
from app.services.runtime.types import ContextPackage, MemoryCandidate, MetaDecision, RuntimeEvent
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


class _FakeSession:
    def __init__(self):
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1


def _meta(relation_delta: int) -> MetaDecision:
    return MetaDecision(
        decision="reply",
        relation_delta=relation_delta,
        persona_patch={},
        tag_ops=[],
        internal_thought="test",
    )


def test_apply_state_patch_clamps_relation_score_to_configured_range():
    service = SideEffects(audit_service=SimpleNamespace(), memory_service=SimpleNamespace())
    session = _FakeSession()
    context = SimpleNamespace(
        session_state=SimpleNamespace(relation_score=99, persona_json={}, active_tags_json=[]),
        runtime_event=SimpleNamespace(event_type="chat"),
        external_context={},
    )

    updated = service.apply_state_patch(session, context, _meta(10))

    assert updated.relation_score == 100
    assert session.flush_count == 1

    updated = service.apply_state_patch(session, context, _meta(-500))

    assert updated.relation_score == 0


def test_apply_state_patch_uses_default_relation_score_when_state_is_missing():
    service = SideEffects(audit_service=SimpleNamespace(), memory_service=SimpleNamespace())
    session = _FakeSession()
    context = SimpleNamespace(
        session_state=SimpleNamespace(relation_score=None, persona_json={}, active_tags_json=[]),
        runtime_event=SimpleNamespace(event_type="chat"),
        external_context={},
    )

    updated = service.apply_state_patch(session, context, _meta(5))

    assert updated.relation_score == 55


def test_side_effects_prefers_valid_context_memory_owner_over_invalid_model_owner():
    session_factory = _session_factory()
    side_effects = SideEffects(
        audit_service=SimpleNamespace(),
        memory_service=SimpleNamespace(index_memory_chunk=lambda *args, **kwargs: None),
    )

    with session_factory() as session:
        user = User(id="user-1", username="owner", password_hash="hash")
        character = Character(
            id="character-1",
            name="Guide",
            prompt_summary="",
            settings_json={},
            created_by_user_id=user.id,
        )
        cocoon = Cocoon(
            id="cocoon-1",
            name="Solo",
            owner_user_id=user.id,
            character_id=character.id,
            selected_model_id="model-1",
        )
        state = SessionState(cocoon_id=cocoon.id, persona_json={}, active_tags_json=[])
        session.add_all([user, character, cocoon, state])
        session.flush()

        context = ContextPackage(
            runtime_event=RuntimeEvent(
                event_type="chat",
                cocoon_id=cocoon.id,
                chat_group_id=None,
                action_id="action-1",
                payload={},
            ),
            conversation=cocoon,
            character=character,
            session_state=state,
            visible_messages=[],
            memory_context=[],
            memory_owner_user_id=user.id,
            external_context={},
        )
        action = ActionDispatch(cocoon_id=cocoon.id, event_type="chat", payload_json={})
        session.add(action)
        session.flush()

        memories = side_effects.persist_memory_candidates(
            session,
            context,
            action,
            [
                MemoryCandidate(
                    scope="dialogue",
                    summary="Reminder request",
                    content="The user asked for a reminder.",
                    owner_user_id="ken",
                    importance=7,
                )
            ],
        )

        assert len(memories) == 1
        assert memories[0].owner_user_id == user.id


def test_persist_thought_message_stores_internal_thought_and_wakeup_summary():
    session_factory = _session_factory()
    side_effects = SideEffects(
        audit_service=SimpleNamespace(),
        memory_service=SimpleNamespace(index_memory_chunk=lambda *args, **kwargs: None),
    )

    with session_factory() as session:
        user = User(id="user-1", username="owner", password_hash="hash")
        character = Character(
            id="character-1",
            name="Guide",
            prompt_summary="",
            settings_json={},
            created_by_user_id=user.id,
        )
        cocoon = Cocoon(
            id="cocoon-1",
            name="Solo",
            owner_user_id=user.id,
            character_id=character.id,
            selected_model_id="model-1",
        )
        state = SessionState(cocoon_id=cocoon.id, persona_json={}, active_tags_json=["focus"])
        action = ActionDispatch(cocoon_id=cocoon.id, event_type="wakeup", payload_json={})
        session.add_all([user, character, cocoon, state, action])
        session.flush()

        context = ContextPackage(
            runtime_event=RuntimeEvent(
                event_type="wakeup",
                cocoon_id=cocoon.id,
                chat_group_id=None,
                action_id="action-1",
                payload={"reason": "scheduled reminder"},
            ),
            conversation=cocoon,
            character=character,
            session_state=state,
            visible_messages=[],
            memory_context=[],
            external_context={},
        )

        message = side_effects.persist_thought_message(
            session,
            context,
            action,
            MetaDecision(
                decision="silence",
                relation_delta=0,
                persona_patch={},
                tag_ops=[],
                internal_thought="Keep the reminder queued quietly.",
                event_summary="Scheduled reminder observed without sending a visible reply.",
            ),
        )

        assert message.is_thought is True
        assert message.role == "assistant"
        assert message.content == "Keep the reminder queued quietly."
        assert message.retraction_note == "Scheduled reminder observed without sending a visible reply."
        assert message.tags_json == ["focus"]
