from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import ActionDispatch, DurableJob, SessionState, WakeupTask
from app.models.entities import DurableJobStatus


def test_chat_round_schedules_default_idle_wakeup(client, worker_runtime, auth_headers, default_cocoon_id):
    response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "Hello there",
            "client_request_id": "idle-default-1",
            "timezone": "UTC",
            "recent_turn_count": 1,
            "idle_seconds": 600,
        },
    )
    assert response.status_code == 202, response.text

    assert worker_runtime.process_next_chat_dispatch() is True

    with client.app.state.container.session_factory() as session:
        task = session.scalars(
            select(WakeupTask)
            .where(WakeupTask.cocoon_id == default_cocoon_id)
            .order_by(WakeupTask.created_at.desc())
        ).first()
        state = session.get(SessionState, default_cocoon_id)
        assert task is not None
        assert state is not None
        assert task.status == DurableJobStatus.queued
        assert task.payload_json["trigger_kind"] == "idle_timeout"
        assert "quiet since" in task.reason
        silence_started_at = datetime.fromisoformat(task.payload_json["silence_started_at"])
        delay_seconds = (task.run_at - silence_started_at).total_seconds()
        assert 295 <= delay_seconds <= 305
        assert state.current_wakeup_task_id == task.id


def test_frequent_cocoon_chat_shortens_idle_wakeup_delay(client, worker_runtime, auth_headers, default_cocoon_id):
    response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "We have been chatting a lot",
            "client_request_id": "idle-fast-1",
            "timezone": "UTC",
            "recent_turn_count": 4,
            "idle_seconds": 45,
        },
    )
    assert response.status_code == 202, response.text

    assert worker_runtime.process_next_chat_dispatch() is True

    with client.app.state.container.session_factory() as session:
        task = session.scalars(
            select(WakeupTask)
            .where(WakeupTask.cocoon_id == default_cocoon_id)
            .order_by(WakeupTask.created_at.desc())
        ).first()
        assert task is not None
        silence_started_at = datetime.fromisoformat(task.payload_json["silence_started_at"])
        delay_seconds = (task.run_at - silence_started_at).total_seconds()
        assert 115 <= delay_seconds <= 125


def test_meta_can_schedule_multiple_wakeups_and_cancel_specific_ones(
    client,
    worker_runtime,
    auth_headers,
    default_cocoon_id,
):
    first = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "Please schedule two wakeups",
            "client_request_id": "multi-wakeup-1",
            "timezone": "UTC",
        },
    )
    assert first.status_code == 202, first.text
    assert worker_runtime.process_next_chat_dispatch() is True

    with client.app.state.container.session_factory() as session:
        queued_tasks = list(
            session.scalars(
                select(WakeupTask)
                .where(WakeupTask.cocoon_id == default_cocoon_id, WakeupTask.status == DurableJobStatus.queued)
                .order_by(WakeupTask.run_at.asc(), WakeupTask.created_at.asc())
            ).all()
        )
        state = session.get(SessionState, default_cocoon_id)
        assert len(queued_tasks) == 2
        assert all(task.reason for task in queued_tasks)
        assert state is not None
        assert state.current_wakeup_task_id == queued_tasks[0].id

    second = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "Please cancel wakeup",
            "client_request_id": "multi-wakeup-2",
            "timezone": "UTC",
        },
    )
    assert second.status_code == 202, second.text
    assert worker_runtime.process_next_chat_dispatch() is True

    with client.app.state.container.session_factory() as session:
        queued_tasks = list(
            session.scalars(
                select(WakeupTask)
                .where(WakeupTask.cocoon_id == default_cocoon_id, WakeupTask.status == DurableJobStatus.queued)
                .order_by(WakeupTask.run_at.asc(), WakeupTask.created_at.asc())
            ).all()
        )
        cancelled_tasks = list(
            session.scalars(
                select(WakeupTask)
                .where(WakeupTask.cocoon_id == default_cocoon_id, WakeupTask.status == DurableJobStatus.cancelled)
                .order_by(WakeupTask.created_at.asc())
            ).all()
        )
        state = session.get(SessionState, default_cocoon_id)
        assert len(cancelled_tasks) >= 1
        assert len(queued_tasks) == 1
        assert state is not None
        assert state.current_wakeup_task_id == queued_tasks[0].id


def test_idle_wakeup_execution_carries_reason_and_time_context(client, worker_runtime, auth_headers, default_cocoon_id):
    response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "Let us check idle followup execution",
            "client_request_id": "idle-exec-1",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 202, response.text
    assert worker_runtime.process_next_chat_dispatch() is True

    with client.app.state.container.session_factory() as session:
        task = session.scalars(
            select(WakeupTask)
            .where(WakeupTask.cocoon_id == default_cocoon_id, WakeupTask.status == DurableJobStatus.queued)
            .order_by(WakeupTask.created_at.desc())
        ).first()
        assert task is not None
        job = session.get(DurableJob, task.payload_json["durable_job_id"])
        assert job is not None
        now = datetime.now(UTC).replace(tzinfo=None)
        task.run_at = now - timedelta(seconds=1)
        job.available_at = now - timedelta(seconds=1)
        session.commit()
        wakeup_task_id = task.id
        wakeup_reason = task.reason

    assert worker_runtime.process_next_durable_job() is True

    with client.app.state.container.session_factory() as session:
        wakeup_action = session.scalars(
            select(ActionDispatch)
            .where(ActionDispatch.cocoon_id == default_cocoon_id, ActionDispatch.event_type == "wakeup")
            .order_by(ActionDispatch.created_at.desc())
        ).first()
        task = session.get(WakeupTask, wakeup_task_id)
        state = session.get(SessionState, default_cocoon_id)
        assert wakeup_action is not None
        assert task is not None
        assert task.status == DurableJobStatus.completed
        assert wakeup_action.payload_json["reason"] == wakeup_reason
        assert wakeup_action.payload_json["trigger_kind"] == "idle_timeout"
        assert wakeup_action.payload_json["idle_summary"]
        assert state is not None
        assert state.current_wakeup_task_id is None

