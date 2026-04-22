import pytest
from sqlalchemy import select

from app.models import ActionDispatch, AuditArtifact, AuditRun, Character, Cocoon, MemoryChunk, SessionState, TagRegistry
from app.services.runtime.reply_delivery_service import ReplyDeliveryService
from app.services.runtime.state_patch_service import StatePatchService
from app.services.runtime.types import (
    ContextPackage,
    GenerationOutput,
    MemoryCandidate,
    MetaDecision,
    RuntimeEvent,
    TagOperation,
    TagReference,
)

pytestmark = pytest.mark.integration


class RecordingHub:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def publish(self, cocoon_id: str, payload: dict) -> None:
        self.events.append((cocoon_id, payload))


def _build_context(session, cocoon_id: str) -> ContextPackage:
    cocoon = session.get(Cocoon, cocoon_id)
    assert cocoon is not None
    character = session.get(Character, cocoon.character_id)
    assert character is not None
    state = session.get(SessionState, cocoon_id)
    assert state is not None
    return ContextPackage(
        runtime_event=RuntimeEvent(
            event_type="message",
            cocoon_id=cocoon_id,
            chat_group_id=None,
            action_id="runtime-action-1",
            payload={},
        ),
        conversation=cocoon,
        character=character,
        session_state=state,
        visible_messages=[],
        memory_context=[],
        memory_hits=[],
        external_context={},
    )


def test_round_preparation_service_creates_runtime_event_and_audit_run(client, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        action = ActionDispatch(
            cocoon_id=default_cocoon_id,
            event_type="message",
            payload_json={"content": "hello"},
        )
        session.add(action)
        session.commit()
        action_id = action.id

    with container.session_factory() as session:
        action = session.get(ActionDispatch, action_id)
        assert action is not None
        event, audit_run = container.round_preparation_service.prepare(session, action)
        session.commit()

        assert event.event_type == "message"
        assert event.action_id == action_id
        persisted_run = session.get(AuditRun, audit_run.id)
        assert persisted_run is not None
        assert persisted_run.operation_type == "message"


def test_state_patch_service_updates_session_state_and_broadcasts(client, default_cocoon_id):
    container = client.app.state.container
    hub = RecordingHub()
    service = StatePatchService(container.side_effects, hub)

    with container.session_factory() as session:
        state = session.get(SessionState, default_cocoon_id)
        assert state is not None
        state.relation_score = 0
        state.persona_json = {}
        state.active_tags_json = []
        context = _build_context(session, default_cocoon_id)
        meta = MetaDecision(
            decision="reply",
            relation_delta=3,
            persona_patch={"tone": "warm"},
            tag_ops=[TagOperation(action="add", tag="focus")],
            internal_thought="",
            next_wakeup_hints=[],
            cancel_wakeup_task_ids=[],
        )

        updated_state = service.apply_and_publish(
            session,
            context,
            meta,
            action_id="action-123",
        )
        session.commit()

        assert updated_state.relation_score == 3
        assert updated_state.persona_json["tone"] == "warm"
        assert updated_state.active_tags_json == ["focus"]
        assert hub.events == [
            (
                f"cocoon:{default_cocoon_id}",
                {
                    "type": "state_patch",
                    "action_id": "action-123",
                    "cocoon_id": default_cocoon_id,
                    "chat_group_id": None,
                    "relation_score": 3,
                    "persona_json": {"tone": "warm"},
                    "active_tags": ["focus"],
                    "current_wakeup_task_id": None,
                },
            )
        ]


def test_reply_delivery_service_persists_reply_and_records_artifact(client, default_cocoon_id):
    container = client.app.state.container
    hub = RecordingHub()
    service = ReplyDeliveryService(container.side_effects, container.audit_service, hub)

    with container.session_factory() as session:
        state = session.get(SessionState, default_cocoon_id)
        assert state is not None
        state.active_tags_json = ["focus"]
        context = _build_context(session, default_cocoon_id)
        action = ActionDispatch(
            cocoon_id=default_cocoon_id,
            event_type="message",
            payload_json={"content": "hello"},
        )
        session.add(action)
        session.flush()
        audit_run = container.audit_service.start_run(
            session=session,
            cocoon_id=default_cocoon_id,
            chat_group_id=None,
            action=action,
            operation_type="message",
        )
        generator_step = container.audit_service.start_step(session, audit_run, "generator_node")

        message = service.deliver(
            session,
            context,
            action,
            audit_run,
            generator_step,
            GenerationOutput(
                rendered_prompt="prompt",
                chunks=["hello", " world"],
                reply_text="hello world",
                raw_response={"ok": True},
                structured_output={"reply_text": "hello world"},
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                provider_kind="mock",
                model_name="mock-model",
            ),
        )
        session.commit()

        stored_memory = session.scalars(
            select(MemoryChunk).where(MemoryChunk.source_message_id == message.id)
        ).first()
        artifact = session.scalars(
            select(AuditArtifact).where(AuditArtifact.run_id == audit_run.id)
        ).first()

        assert message.content == "hello world"
        assert stored_memory is None
        assert artifact is not None
        assert [payload["type"] for _, payload in hub.events] == ["reply_started", "reply_chunk", "reply_chunk", "reply_done"]


def test_side_effects_persist_memory_candidates_without_copying_reply_text(client, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        state = session.get(SessionState, default_cocoon_id)
        assert state is not None
        state.active_tags_json = ["focus"]
        context = _build_context(session, default_cocoon_id)
        action = ActionDispatch(
            cocoon_id=default_cocoon_id,
            event_type="message",
            payload_json={"content": "I prefer jasmine tea"},
        )
        session.add(action)
        session.flush()
        message = container.side_effects.persist_generated_message(
            session,
            context,
            action,
            GenerationOutput(
                rendered_prompt="prompt",
                chunks=["Noted."],
                reply_text="Noted, I will remember that.",
                raw_response={"ok": True},
                structured_output={"reply_text": "Noted, I will remember that."},
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                provider_kind="mock",
                model_name="mock-model",
            ),
        )
        memories = container.side_effects.persist_memory_candidates(
            session,
            context,
            action,
            [
                MemoryCandidate(
                    scope="dialogue",
                    summary="User prefers jasmine tea",
                    content="The user said they prefer jasmine tea.",
                    tags=[TagReference(tag="focus")],
                    importance=7,
                )
            ],
            source_message=message,
        )
        session.commit()

        assert len(memories) == 1
        assert memories[0].summary == "User prefers jasmine tea"
        assert memories[0].content == "The user said they prefer jasmine tea."
        assert memories[0].content != message.content


def test_side_effects_resolve_readable_tag_references_to_canonical_ids(client, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        tag = TagRegistry(
            tag_id="focus",
            brief="Focus topic",
            visibility="public",
            meta_json={"name": "Focus Topic"},
        )
        session.add(tag)
        session.flush()
        state = session.get(SessionState, default_cocoon_id)
        assert state is not None
        context = _build_context(session, default_cocoon_id)
        context.external_context["tag_catalog_by_ref"] = {
            tag.id: {
                "id": tag.id,
                "tag_id": tag.tag_id,
                "brief": tag.brief,
                "visibility": tag.visibility,
                "is_isolated": tag.is_isolated,
                "meta_json": tag.meta_json,
            },
            tag.tag_id: {
                "id": tag.id,
                "tag_id": tag.tag_id,
                "brief": tag.brief,
                "visibility": tag.visibility,
                "is_isolated": tag.is_isolated,
                "meta_json": tag.meta_json,
            },
        }

        action = ActionDispatch(
            cocoon_id=default_cocoon_id,
            event_type="message",
            payload_json={"content": "remember focus topic"},
        )
        session.add(action)
        session.flush()

        meta = MetaDecision(
            decision="reply",
            relation_delta=0,
            persona_patch={},
            tag_ops=[TagOperation(action="add", tag="Focus Topic")],
            internal_thought="",
            next_wakeup_hints=[],
            cancel_wakeup_task_ids=[],
        )
        container.side_effects.apply_state_patch(session, context, meta)

        memories = container.side_effects.persist_memory_candidates(
            session,
            context,
            action,
            [
                MemoryCandidate(
                    scope="dialogue",
                    summary="Focus preference",
                    content="The user asked to remember the focus topic.",
                    tags=[TagReference(tag="Focus Topic")],
                    importance=6,
                )
            ],
        )
        session.commit()

        assert state.active_tags_json == [tag.id]
        assert len(memories) == 1
        assert memories[0].tags_json == [tag.id]
