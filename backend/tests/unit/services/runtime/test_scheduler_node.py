from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import DurableJob, SessionState, WakeupTask
from app.models.entities import DurableJobStatus
from app.services.jobs.durable_jobs import DurableJobService
from app.services.runtime.scheduling.scheduler_node import SchedulerNode
from app.services.runtime.types import ContextPackage, MetaDecision, RuntimeEvent
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def _context(
    *,
    event_type: str = "chat",
    cocoon_id: str | None = "cocoon-1",
    chat_group_id: str | None = None,
    payload: dict | None = None,
    visible_messages: list | None = None,
    max_context_messages: int = 12,
    auto_compaction_enabled: bool = True,
    memory_owner_user_id: str | None = None,
) -> ContextPackage:
    runtime_event = RuntimeEvent(
        event_type=event_type,
        cocoon_id=cocoon_id,
        chat_group_id=chat_group_id,
        action_id="action-1",
        payload=payload or {},
    )
    conversation_id = chat_group_id or cocoon_id or "target-1"
    return ContextPackage(
        runtime_event=runtime_event,
        conversation=SimpleNamespace(
            id=conversation_id,
            name="Demo",
            max_context_messages=max_context_messages,
            auto_compaction_enabled=auto_compaction_enabled,
        ),
        character=SimpleNamespace(id="character-1"),
        session_state=SimpleNamespace(id=conversation_id),
        visible_messages=visible_messages or [],
        memory_context=[],
        memory_owner_user_id=memory_owner_user_id,
        external_context={},
    )


def _meta(*, hints=None, cancelled_ids=None) -> MetaDecision:
    return MetaDecision(
        decision="continue",
        relation_delta=0,
        persona_patch={},
        tag_ops=[],
        internal_thought="",
        next_wakeup_hints=hints or [],
        cancel_wakeup_task_ids=cancelled_ids or [],
    )


def test_scheduler_node_resolves_run_at_variants_and_validates_arguments():
    scheduler = SchedulerNode(DurableJobService())
    aware = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)

    assert scheduler._resolve_run_at({"run_at": aware}) == aware.replace(tzinfo=None)
    assert scheduler._resolve_run_at({"run_at": "2026-04-21T12:30:00+00:00"}) == datetime(2026, 4, 21, 12, 30)
    assert scheduler._resolve_run_at({"delay_seconds": 1}) > datetime.now(UTC).replace(tzinfo=None)
    assert scheduler._resolve_run_at({"delay_minutes": 1}) > datetime.now(UTC).replace(tzinfo=None)
    assert scheduler._resolve_run_at({"delay_hours": 1}) > datetime.now(UTC).replace(tzinfo=None)

    with pytest.raises(ValueError, match="wakeup hint must define run_at or a delay"):
        scheduler._resolve_run_at({})

    session_factory = _session_factory()
    with session_factory() as session:
        session.add(SessionState(cocoon_id="cocoon-1", persona_json={}, active_tags_json=[]))
        session.commit()

        with pytest.raises(TypeError, match="multiple values for argument 'run_at'"):
            scheduler.schedule_wakeup(session, aware, run_at=aware, cocoon_id="cocoon-1", reason="duplicate")

        with pytest.raises(TypeError, match="multiple target identifiers"):
            scheduler.schedule_wakeup(session, "cocoon-1", run_at=aware, cocoon_id="other", reason="duplicate")

        with pytest.raises(TypeError, match="conflicting legacy and keyword arguments"):
            scheduler.schedule_wakeup(session, "cocoon-1", aware, run_at=aware, reason="duplicate")

        with pytest.raises(TypeError, match="at most two positional arguments"):
            scheduler.schedule_wakeup(session, "a", "b", "c", reason="too-many")

        with pytest.raises(TypeError, match="missing required run_at"):
            scheduler.schedule_wakeup(session, cocoon_id="cocoon-1", reason="missing")

        with pytest.raises(ValueError, match="requires a non-empty reason"):
            scheduler.schedule_wakeup(session, "cocoon-1", aware, reason="   ")


def test_scheduler_node_schedule_wakeup_supports_legacy_args_and_updates_current_task():
    session_factory = _session_factory()
    scheduler = SchedulerNode(DurableJobService())
    run_at = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)

    with session_factory() as session:
        session.add(SessionState(cocoon_id="cocoon-1", persona_json={}, active_tags_json=[]))
        session.add(SessionState(chat_group_id="group-1", persona_json={}, active_tags_json=[]))
        session.commit()

        task, job = scheduler.schedule_wakeup(
            session,
            "cocoon-1",
            run_at=run_at,
            reason="  follow up  ",
            payload_json={"source": "unit"},
        )
        task2, job2 = scheduler.schedule_wakeup(
            session,
            run_at,
            chat_group_id="group-1",
            reason="group ping",
            payload_json={},
        )

        assert task.cocoon_id == "cocoon-1"
        assert task.reason == "follow up"
        assert task.payload_json["source"] == "unit"
        assert task.payload_json["durable_job_id"] == job.id
        assert job.lock_key.startswith("cocoon:cocoon-1:wakeup:")
        assert job.available_at == run_at.replace(tzinfo=None)

        assert task2.chat_group_id == "group-1"
        assert task2.payload_json["durable_job_id"] == job2.id
        assert job2.lock_key.startswith("chat-group:group-1:wakeup:")

        cocoon_state = session.get(SessionState, "cocoon-1")
        group_state = session.get(SessionState, "group-1")
        assert cocoon_state is not None and cocoon_state.current_wakeup_task_id == task.id
        assert group_state is not None and group_state.current_wakeup_task_id == task2.id


def test_scheduler_node_schedule_handles_cancellation_hints_and_compaction():
    session_factory = _session_factory()
    scheduler = SchedulerNode(DurableJobService())

    with session_factory() as session:
        session.add(SessionState(cocoon_id="cocoon-1", persona_json={}, active_tags_json=[]))
        session.commit()

        existing_task, _ = scheduler.schedule_wakeup(
            session,
            "cocoon-1",
            datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5),
            reason="existing wakeup",
            payload_json={"trigger_kind": "idle_timeout"},
        )
        visible_messages = [
            SimpleNamespace(
                id=f"message-{index}",
                created_at=datetime.now(UTC).replace(tzinfo=None),
                role="user",
                is_retracted=False,
            )
            for index in range(1, 6)
        ]
        context = _context(
            payload={"timezone": "Asia/Shanghai"},
            visible_messages=visible_messages,
            max_context_messages=5,
        )
        result = scheduler.schedule(
            session,
            context,
            _meta(
                hints=[{"delay_minutes": 10, "reason": "meta follow-up", "payload_json": {"kind": "meta"}}],
                cancelled_ids=[existing_task.id],
            ),
        )

        cancelled_task = session.get(WakeupTask, existing_task.id)
        current_state = session.get(SessionState, "cocoon-1")
        assert result["cancelled_wakeup_task_ids"] == [existing_task.id]
        assert len(result["wakeup_task_ids"]) == 1
        assert result["wakeup_job_id"] == result["wakeup_job_ids"][0]
        assert result["compaction_job_id"] is not None
        assert cancelled_task is not None
        assert cancelled_task.status == DurableJobStatus.cancelled
        scheduled_task = session.get(WakeupTask, result["wakeup_task_id"])
        assert scheduled_task is not None
        assert scheduled_task.payload_json["timezone"] == "Asia/Shanghai"
        compaction_job = session.scalar(select(DurableJob).where(DurableJob.id == result["compaction_job_id"]))
        assert compaction_job is not None
        assert compaction_job.payload_json["before_message_id"] == "message-5"
        assert current_state is not None
        assert current_state.current_wakeup_task_id == result["wakeup_task_id"]


def test_scheduler_node_idle_wakeup_logic_and_delay_resolution():
    session_factory = _session_factory()
    scheduler = SchedulerNode(DurableJobService())

    with session_factory() as session:
        session.add(SessionState(cocoon_id="cocoon-1", persona_json={}, active_tags_json=[]))
        session.commit()

        active_context = _context(
            payload={"recent_turn_count": 3, "timezone": "Asia/Shanghai"},
            visible_messages=[
                SimpleNamespace(
                    id=f"m{i}",
                    role="user" if i % 2 == 0 else "assistant",
                    is_retracted=False,
                    created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5 - i),
                )
                for i in range(4)
            ],
            memory_owner_user_id="user-1",
        )
        result = scheduler.schedule(session, active_context, _meta())
        task = session.get(WakeupTask, result["wakeup_task_id"])
        assert task is not None
        assert task.payload_json["trigger_kind"] == "idle_timeout"
        assert task.payload_json["timezone"] == "Asia/Shanghai"
        assert task.payload_json["memory_owner_user_id"] == "user-1"
        assert result["compaction_job_id"] is None

        assert scheduler._should_schedule_idle_wakeup(session, _context(event_type="merge"), _meta()) is False
        assert scheduler._should_schedule_idle_wakeup(session, _context(), _meta(hints=[{"delay_minutes": 1}])) is False
        assert scheduler._should_schedule_idle_wakeup(session, _context(), _meta()) is False

        assert scheduler._resolve_idle_wakeup_delay_seconds(_context(chat_group_id="group-1", cocoon_id=None)) == scheduler.DEFAULT_IDLE_WAKEUP_DELAY_SECONDS
        assert scheduler._resolve_idle_wakeup_delay_seconds(_context(payload={"idle_seconds": 60})) == scheduler.FREQUENT_COCOON_IDLE_WAKEUP_DELAY_SECONDS
        bursty = _context(
            visible_messages=[
                SimpleNamespace(
                    id=f"b{i}",
                    role="user" if i % 2 == 0 else "assistant",
                    is_retracted=False,
                    created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10 - i),
                )
                for i in range(4)
            ]
        )
        assert scheduler._resolve_idle_wakeup_delay_seconds(bursty) == scheduler.FREQUENT_COCOON_IDLE_WAKEUP_DELAY_SECONDS


def test_scheduler_node_skips_invalid_meta_wakeup_hints_without_crashing():
    session_factory = _session_factory()
    scheduler = SchedulerNode(DurableJobService())

    with session_factory() as session:
        session.add(SessionState(cocoon_id="cocoon-1", persona_json={}, active_tags_json=[]))
        session.commit()

        result = scheduler.schedule(
            session,
            _context(),
            _meta(
                hints=[
                    {"delay_minutes": 5},
                    {"reason": "   ", "delay_minutes": 5},
                    {"reason": "missing delay"},
                ]
            ),
        )

        assert result["wakeup_task_ids"] == []
        current_state = session.get(SessionState, "cocoon-1")
        assert current_state is not None
        assert current_state.current_wakeup_task_id is None


def test_scheduler_node_helpers_cover_job_lookup_and_invalid_idle_payloads():
    session_factory = _session_factory()
    scheduler = SchedulerNode(DurableJobService())

    with session_factory() as session:
        session.add(SessionState(cocoon_id="cocoon-1", persona_json={}, active_tags_json=[]))
        session.commit()

        task, job = scheduler.schedule_wakeup(
            session,
            "cocoon-1",
            datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=1),
            reason="lookup",
            payload_json={},
        )
        assert scheduler._job_for_task(session, task).id == job.id
        assert scheduler._job_for_task(session, SimpleNamespace(payload_json={})) is None
        assert scheduler._schedule_compaction(session, _context(chat_group_id="group-1", cocoon_id=None), reason="skip") is None
        assert (
            scheduler._schedule_compaction(
                session,
                _context(auto_compaction_enabled=False, visible_messages=[SimpleNamespace(id="m1")]),
                reason="skip",
            )
            is None
        )
        assert (
            scheduler._schedule_compaction(
                session,
                _context(max_context_messages=1, visible_messages=[SimpleNamespace(id="m1")]),
                reason="skip",
            )
            is None
        )
        assert scheduler._schedule_compaction(session, _context(visible_messages=[]), reason="skip") is None

        weird_recent_turns = _context(payload={"recent_turn_count": "bad", "idle_seconds": "also-bad"})
        assert scheduler._resolve_idle_wakeup_delay_seconds(weird_recent_turns) == scheduler.DEFAULT_IDLE_WAKEUP_DELAY_SECONDS
