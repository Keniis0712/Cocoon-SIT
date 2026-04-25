from __future__ import annotations

from datetime import datetime, timedelta

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
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def _message(*, id: str, created_at: datetime, role: str = "assistant", action_id: str | None = None) -> Message:
    return Message(
        id=id,
        cocoon_id="cocoon-1",
        action_id=action_id,
        role=role,
        content=id,
        created_at=created_at,
    )


def test_round_cleanup_delete_message_related_rows_deletes_all_linked_records():
    session_factory = _session_factory()
    service = RoundCleanupService()
    now = datetime(2026, 4, 21, 9, 0, 0)

    with session_factory() as session:
        action = ActionDispatch(id="action-1", cocoon_id="cocoon-1", event_type="chat")
        message = _message(id="msg-1", created_at=now, action_id=action.id)
        message_id = message.id
        memory = MemoryChunk(
            id="memory-1",
            cocoon_id="cocoon-1",
            owner_user_id="owner-1",
            character_id="character-1",
            source_message_id=message.id,
            scope="session",
            content="saved",
        )
        memory_id = memory.id
        run = AuditRun(id="run-1", cocoon_id="cocoon-1", action_id=action.id, operation_type="chat")
        run_id = run.id
        step = AuditStep(id="step-1", run_id=run.id, step_name="memory")
        step_id = step.id
        artifact = AuditArtifact(id="artifact-1", run_id=run.id, step_id=step.id, kind="json")
        artifact_id = artifact.id
        link = AuditLink(id="link-1", run_id=run.id, target_artifact_id=artifact.id, relation="produced_by")
        link_id = link.id
        session.add_all(
            [
                action,
                message,
                MessageTag(id="message-tag-1", message_id=message.id, tag_id="tag-1"),
                memory,
                MemoryTag(id="memory-tag-1", memory_chunk_id=memory.id, tag_id="tag-1"),
                run,
                step,
                artifact,
                link,
                FailedRound(id="failed-1", cocoon_id="cocoon-1", action_id=action.id, reason="boom"),
            ]
        )
        session.commit()

        service._delete_message_related_rows(session, [message.id])
        session.commit()
        session.expire_all()

        assert session.scalar(select(Message).where(Message.id == message_id)) is None
        assert session.scalar(select(MemoryChunk).where(MemoryChunk.id == memory_id)) is None
        assert session.scalar(select(AuditRun).where(AuditRun.id == run_id)) is None
        assert session.scalar(select(AuditStep).where(AuditStep.id == step_id)) is None
        assert session.scalar(select(AuditArtifact).where(AuditArtifact.id == artifact_id)) is None
        assert session.scalar(select(AuditLink).where(AuditLink.id == link_id)) is None
        assert session.scalar(select(MessageTag).where(MessageTag.message_id == message_id)) is None
        assert session.scalar(select(MemoryTag).where(MemoryTag.memory_chunk_id == memory_id)) is None
        assert session.scalar(select(FailedRound).where(FailedRound.action_id == action.id)) is None


def test_round_cleanup_delete_message_related_rows_noops_for_empty_ids():
    session_factory = _session_factory()
    service = RoundCleanupService()

    with session_factory() as session:
        service._delete_message_related_rows(session, [])


def test_round_cleanup_for_edit_validates_arguments_and_ignores_missing_target():
    session_factory = _session_factory()
    service = RoundCleanupService()

    with session_factory() as session:
        with pytest.raises(TypeError, match="legacy positional args or keyword target args"):
            service.cleanup_for_edit(session, "cocoon-1", "message-1", cocoon_id="cocoon-1")
        with pytest.raises(TypeError, match="missing required edited_message_id"):
            service.cleanup_for_edit(session, cocoon_id="cocoon-1")

        service.cleanup_for_edit(session, cocoon_id="cocoon-1", edited_message_id="missing")


def test_round_cleanup_for_edit_deletes_messages_after_anchor():
    session_factory = _session_factory()
    service = RoundCleanupService()
    base = datetime(2026, 4, 21, 10, 0, 0)

    with session_factory() as session:
        first = _message(id="msg-1", created_at=base, role="user")
        second = _message(id="msg-2", created_at=base + timedelta(minutes=1))
        third = _message(id="msg-3", created_at=base + timedelta(minutes=2))
        second_id = second.id
        third_id = third.id
        session.add_all([first, second, third])
        session.commit()

        service.cleanup_for_edit(session, "cocoon-1", first.id)
        session.commit()
        session.expire_all()

        assert session.get(Message, first.id) is not None
        assert session.scalar(select(Message).where(Message.id == second_id)) is None
        assert session.scalar(select(Message).where(Message.id == third_id)) is None


def test_round_cleanup_for_retry_validates_args_and_uses_anchor_when_present():
    session_factory = _session_factory()
    service = RoundCleanupService()
    base = datetime(2026, 4, 21, 11, 0, 0)

    with session_factory() as session:
        with pytest.raises(TypeError, match="legacy positional args or keyword target args"):
            service.cleanup_for_retry(session, "a", "b", "c")

        early = _message(id="assistant-1", created_at=base)
        anchor = _message(id="assistant-2", created_at=base + timedelta(minutes=1))
        latest = _message(id="assistant-3", created_at=base + timedelta(minutes=2))
        latest_id = latest.id
        session.add_all([early, anchor, latest])
        session.commit()

        service.cleanup_for_retry(session, cocoon_id="cocoon-1", message_id=anchor.id)
        session.commit()
        session.expire_all()

        assert session.get(Message, early.id) is not None
        assert session.get(Message, anchor.id) is not None
        assert session.scalar(select(Message).where(Message.id == latest_id)) is None


def test_round_cleanup_for_retry_falls_back_when_anchor_missing():
    session_factory = _session_factory()
    service = RoundCleanupService()
    base = datetime(2026, 4, 21, 12, 0, 0)

    with session_factory() as session:
        latest = _message(id="assistant-1", created_at=base)
        latest_id = latest.id
        session.add(latest)
        session.commit()

        service.cleanup_for_retry(session, cocoon_id="cocoon-1", message_id="missing-anchor")
        session.commit()
        session.expire_all()

        assert session.scalar(select(Message).where(Message.id == latest_id)) is None
