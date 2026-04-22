from types import SimpleNamespace

from app.models import CocoonMergeJob, CocoonPullJob, DurableJob, SessionState, WakeupTask
from app.models.entities import DurableJobStatus
from app.worker.jobs.runtime_job_service import RuntimeJobService


class _FakeSession:
    def __init__(self, *, task=None, scalar_results=None):
        self.task = task
        self.scalar_results = list(scalar_results or [])

    def get(self, model, object_id):
        assert model is WakeupTask
        return self.task

    def scalar(self, statement):
        return self.scalar_results.pop(0) if self.scalar_results else None


def test_execute_wakeup_short_circuits_cancelled_tasks(monkeypatch):
    sync_calls = []
    action_calls = []
    run_calls = []
    task = WakeupTask(
        id="wake-1",
        cocoon_id="cocoon-1",
        run_at="2026-04-21T00:00:00",
        status=DurableJobStatus.cancelled,
    )
    service = RuntimeJobService(
        chat_runtime=SimpleNamespace(run=lambda session, action: run_calls.append((session, action))),
        runtime_action_service=SimpleNamespace(
            create_runtime_action=lambda *args, **kwargs: action_calls.append((args, kwargs))
        ),
    )
    monkeypatch.setattr(
        "app.worker.jobs.runtime_job_service.sync_current_wakeup_task_id",
        lambda session, **kwargs: sync_calls.append((session, kwargs)),
    )

    session = _FakeSession(task=task)

    service.execute_wakeup(
        session,
        DurableJob(cocoon_id="cocoon-1", job_type="wakeup", lock_key="lock", payload_json={"wakeup_task_id": "wake-1"}),
    )

    assert action_calls == []
    assert run_calls == []
    assert sync_calls == [(session, {"cocoon_id": "cocoon-1", "chat_group_id": None})]


def test_execute_wakeup_runs_runtime_and_clears_current_task(monkeypatch):
    sync_calls = []
    state = SessionState(cocoon_id="cocoon-1", current_wakeup_task_id="wake-1", persona_json={}, active_tags_json=[])
    task = WakeupTask(
        id="wake-1",
        cocoon_id="cocoon-1",
        run_at="2026-04-21T00:00:00",
        reason="idle",
        payload_json={"origin": "scheduler"},
        status=DurableJobStatus.queued,
    )
    created_actions = []
    run_calls = []
    monkeypatch.setattr("app.worker.jobs.runtime_job_service.get_session_state", lambda *args, **kwargs: state)
    monkeypatch.setattr(
        "app.worker.jobs.runtime_job_service.sync_current_wakeup_task_id",
        lambda session, **kwargs: sync_calls.append((session, kwargs)),
    )
    service = RuntimeJobService(
        chat_runtime=SimpleNamespace(run=lambda session, action: run_calls.append((session, action))),
        runtime_action_service=SimpleNamespace(
            create_runtime_action=lambda session, **kwargs: created_actions.append(kwargs) or SimpleNamespace(id="action-1")
        ),
    )
    session = _FakeSession(task=task)
    job = DurableJob(
        cocoon_id="cocoon-1",
        job_type="wakeup",
        lock_key="lock",
        payload_json={"wakeup_task_id": "wake-1"},
    )

    service.execute_wakeup(session, job)

    assert task.status == DurableJobStatus.completed
    assert state.current_wakeup_task_id is None
    assert created_actions == [
        {
            "event_type": "wakeup",
            "payload_json": {"wakeup_task_id": "wake-1", "reason": "idle", "origin": "scheduler"},
            "cocoon_id": "cocoon-1",
            "chat_group_id": None,
        }
    ]
    assert run_calls == [(session, SimpleNamespace(id="action-1"))]
    assert sync_calls == [(session, {"cocoon_id": "cocoon-1", "chat_group_id": None})]


def test_execute_pull_marks_pull_job_completed():
    pull_job = CocoonPullJob(
        durable_job_id="job-1",
        source_cocoon_id="source-1",
        target_cocoon_id="target-1",
    )
    created_action = SimpleNamespace(id="action-pull")
    run_calls = []
    service = RuntimeJobService(
        chat_runtime=SimpleNamespace(run=lambda session, action: run_calls.append((session, action))),
        runtime_action_service=SimpleNamespace(create_runtime_action=lambda *args, **kwargs: created_action),
    )
    session = _FakeSession(scalar_results=[pull_job])
    job = DurableJob(id="job-1", cocoon_id="target-1", job_type="pull", lock_key="lock", payload_json={"x": 1})

    service.execute_pull(session, job)

    assert run_calls == [(session, created_action)]
    assert pull_job.status == DurableJobStatus.completed
    assert pull_job.summary_json == {"action_id": "action-pull"}


def test_execute_merge_marks_merge_job_completed():
    merge_job = CocoonMergeJob(
        durable_job_id="job-2",
        source_cocoon_id="source-1",
        target_cocoon_id="target-1",
    )
    created_action = SimpleNamespace(id="action-merge")
    run_calls = []
    service = RuntimeJobService(
        chat_runtime=SimpleNamespace(run=lambda session, action: run_calls.append((session, action))),
        runtime_action_service=SimpleNamespace(create_runtime_action=lambda *args, **kwargs: created_action),
    )
    session = _FakeSession(scalar_results=[merge_job])
    job = DurableJob(id="job-2", cocoon_id="target-1", job_type="merge", lock_key="lock", payload_json={"x": 2})

    service.execute_merge(session, job)

    assert run_calls == [(session, created_action)]
    assert merge_job.status == DurableJobStatus.completed
    assert merge_job.summary_json == {"action_id": "action-merge"}
