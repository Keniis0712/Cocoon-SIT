from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    ActionDispatch,
    AuditArtifact,
    AuditLink,
    AuditRun,
    AuditStep,
    FailedRound,
    MemoryChunk,
    MemoryTag,
    Message,
    MessageTag,
)
from app.services.runtime.orchestration.round_cleanup import RoundCleanupService

pytestmark = pytest.mark.integration


def test_round_cleanup_for_retry_removes_assistant_side_effects(client, default_cocoon_id):
    container = client.app.state.container
    service = RoundCleanupService()
    with container.session_factory() as session:
        action = ActionDispatch(cocoon_id=default_cocoon_id, event_type="chat", status="completed")
        session.add(action)
        session.flush()
        user_message = Message(cocoon_id=default_cocoon_id, role="user", content="Keep me")
        assistant_message = Message(
            cocoon_id=default_cocoon_id,
            action_id=action.id,
            role="assistant",
            content="Delete me",
        )
        session.add_all([user_message, assistant_message])
        session.flush()
        session.add(MessageTag(message_id=assistant_message.id, tag_id="ops"))
        memory = MemoryChunk(
            cocoon_id=default_cocoon_id,
            source_message_id=assistant_message.id,
            scope="dialogue",
            content="Delete memory",
        )
        session.add(memory)
        session.flush()
        session.add(MemoryTag(memory_chunk_id=memory.id, tag_id="ops"))
        run = AuditRun(cocoon_id=default_cocoon_id, action_id=action.id, operation_type="chat")
        session.add(run)
        session.flush()
        step = AuditStep(run_id=run.id, step_name="generator_node")
        session.add(step)
        session.flush()
        artifact = AuditArtifact(run_id=run.id, step_id=step.id, kind="generator_output", metadata_json={})
        session.add(artifact)
        session.flush()
        session.add(
            AuditLink(
                run_id=run.id,
                source_step_id=step.id,
                target_artifact_id=artifact.id,
                relation="produced_by",
            )
        )
        session.add(FailedRound(cocoon_id=default_cocoon_id, action_id=action.id, reason="x"))
        session.commit()
        user_message_id = user_message.id
        assistant_message_id = assistant_message.id

    with container.session_factory() as session:
        service.cleanup_for_retry(session, default_cocoon_id)
        session.commit()

    with container.session_factory() as session:
        assert session.get(Message, user_message_id) is not None
        assert session.get(Message, assistant_message_id) is None
        assert session.scalars(select(MemoryChunk).where(MemoryChunk.cocoon_id == default_cocoon_id)).first() is None
        assert session.scalars(select(AuditRun).where(AuditRun.action_id == action.id)).first() is None
        assert session.scalars(select(AuditStep).where(AuditStep.run_id == run.id)).first() is None
        assert session.scalars(select(AuditArtifact).where(AuditArtifact.run_id == run.id)).first() is None
        assert session.scalars(select(AuditLink).where(AuditLink.run_id == run.id)).first() is None
        assert session.scalars(select(FailedRound).where(FailedRound.action_id == action.id)).first() is None


def test_round_cleanup_for_edit_removes_later_messages(client, default_cocoon_id):
    container = client.app.state.container
    service = RoundCleanupService()
    base_time = datetime.now(UTC).replace(tzinfo=None)
    with container.session_factory() as session:
        target = Message(
            cocoon_id=default_cocoon_id,
            role="user",
            content="Original",
            created_at=base_time,
        )
        later_assistant = Message(
            cocoon_id=default_cocoon_id,
            role="assistant",
            content="Later assistant",
            created_at=base_time + timedelta(seconds=1),
        )
        later_user = Message(
            cocoon_id=default_cocoon_id,
            role="user",
            content="Later user",
            created_at=base_time + timedelta(seconds=2),
        )
        session.add_all([target, later_assistant, later_user])
        session.commit()
        target_id = target.id
        later_assistant_id = later_assistant.id
        later_user_id = later_user.id

    with container.session_factory() as session:
        service.cleanup_for_edit(session, default_cocoon_id, target_id)
        session.commit()

    with container.session_factory() as session:
        assert session.get(Message, target_id) is not None
        assert session.get(Message, later_assistant_id) is None
        assert session.get(Message, later_user_id) is None
