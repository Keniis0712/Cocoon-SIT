from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import ActionDispatch, DurableJob, SessionState, WakeupTask

pytestmark = pytest.mark.integration


def test_future_wakeup_job_respects_run_at(client, worker_runtime, auth_headers, default_cocoon_id):
    run_at = datetime.now(UTC) + timedelta(minutes=20)
    container = client.app.state.container
    with container.session_factory() as session:
        task, job = container.scheduler_node.schedule_wakeup(
            session,
            cocoon_id=default_cocoon_id,
            run_at=run_at,
            reason="future follow-up",
            payload_json={"scheduled_by": "test"},
        )
        session.commit()
        task_id = task.id
        job_id = job.id

    assert worker_runtime.process_next_durable_job() is False

    with client.app.state.container.session_factory() as session:
        task = session.get(WakeupTask, task_id)
        job = session.get(DurableJob, job_id)
        state = session.get(SessionState, default_cocoon_id)
        assert task is not None
        assert job is not None
        assert state is not None
        assert task.reason == "future follow-up"
        assert task.status == "queued"
        assert job.status == "queued"
        assert abs((job.available_at - run_at.replace(tzinfo=None)).total_seconds()) < 2
        assert state.current_wakeup_task_id == task.id


def test_user_wakeup_command_no_longer_creates_command_driven_wakeup(
    client,
    worker_runtime,
    auth_headers,
    default_cocoon_id,
):
    response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "/wakeup 15m Check back with the user",
            "client_request_id": "schedule-followup-1",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 202, response.text
    assert worker_runtime.process_next_chat_dispatch() is True
    assert worker_runtime.process_next_durable_job() is False

    with client.app.state.container.session_factory() as session:
        action = session.scalar(
            select(ActionDispatch).where(ActionDispatch.client_request_id == "schedule-followup-1")
        )
        state = session.get(SessionState, default_cocoon_id)
        tasks = list(session.scalars(select(WakeupTask)).all())
        wakeup_jobs = list(session.scalars(select(DurableJob).where(DurableJob.job_type == "wakeup")).all())
        assert action is not None
        assert action.status == "completed"
        assert state is not None
        assert len(tasks) == 1
        assert len(wakeup_jobs) == 1
        assert tasks[0].payload_json["trigger_kind"] == "idle_timeout"
        assert tasks[0].reason != "Check back with the user"
        assert state.current_wakeup_task_id == tasks[0].id
