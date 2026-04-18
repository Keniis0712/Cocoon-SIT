from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import ActionDispatch, DurableJob, SessionState, WakeupTask


def test_future_wakeup_job_respects_run_at(client, worker_runtime, auth_headers, default_cocoon_id):
    run_at = datetime.now(UTC) + timedelta(minutes=20)
    response = client.post(
        "/api/v1/wakeup",
        headers=auth_headers,
        json={
            "cocoon_id": default_cocoon_id,
            "reason": "future follow-up",
            "run_at": run_at.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert worker_runtime.process_next_durable_job() is False

    with client.app.state.container.session_factory() as session:
        task = session.get(WakeupTask, payload["task_id"])
        job = session.get(DurableJob, payload["job_id"])
        state = session.get(SessionState, default_cocoon_id)
        assert task is not None
        assert job is not None
        assert state is not None
        assert task.reason == "future follow-up"
        assert task.status == "queued"
        assert job.status == "queued"
        assert abs((job.available_at - run_at.replace(tzinfo=None)).total_seconds()) < 2
        assert state.current_wakeup_task_id == task.id


def test_chat_round_can_schedule_followup_wakeup(
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
        assert action is not None
        assert action.status == "completed"
        assert state is not None
        assert state.current_wakeup_task_id is not None

        task = session.get(WakeupTask, state.current_wakeup_task_id)
        assert task is not None
        assert task.reason == "Check back with the user"
        assert task.status == "queued"
        assert task.payload_json["scheduled_by"] == "meta_command"
        assert task.payload_json["source_action_id"] == action.id

        job = session.get(DurableJob, task.payload_json["durable_job_id"])
        assert job is not None
        assert job.status == "queued"
        assert job.available_at > datetime.now(UTC).replace(tzinfo=None)
