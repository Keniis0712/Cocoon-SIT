from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import ActionDispatch, AuditArtifact, Checkpoint, DurableJob, MemoryChunk, Message, WakeupTask
from app.worker.durable_executor import DurableJobExecutor
from app.worker.runtime import WorkerRuntime

pytestmark = pytest.mark.integration


def _build_durable_executor(container) -> DurableJobExecutor:
    return DurableJobExecutor(
        chat_runtime=container.chat_runtime,
        durable_jobs=container.durable_jobs,
        audit_service=container.audit_service,
        round_cleanup=container.round_cleanup,
        prompt_service=container.prompt_service,
        provider_registry=container.provider_registry,
    )


def _build_worker_runtime(container) -> WorkerRuntime:
    return WorkerRuntime(
        session_factory=container.session_factory,
        chat_queue=container.chat_queue,
        chat_runtime=container.chat_runtime,
        durable_jobs=container.durable_jobs,
        durable_executor=_build_durable_executor(container),
        realtime_hub=container.realtime_hub,
        worker_name=container.settings.durable_job_worker_name,
    )


def test_runtime_action_service_creates_running_action(client, default_cocoon_id):
    container = client.app.state.container
    service = _build_durable_executor(container).runtime_action_service

    with container.session_factory() as session:
        action = service.create_runtime_action(
            session,
            default_cocoon_id,
            "wakeup",
            {"reason": "service test"},
        )
        session.commit()
        assert action.event_type == "wakeup"
        assert action.status == "running"


def test_artifact_cleanup_job_service_deletes_explicit_artifacts(client, auth_headers, default_cocoon_id):
    container = client.app.state.container
    durable_executor = _build_durable_executor(container)
    client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "artifact cleanup source", "client_request_id": "artifact-clean-1", "timezone": "UTC"},
    )
    with container.session_factory() as session:
        action = session.scalars(select(ActionDispatch).where(ActionDispatch.client_request_id == "artifact-clean-1")).first()
        assert action is not None
    runtime = _build_worker_runtime(container)
    assert runtime.process_next_chat_dispatch() is True

    with container.session_factory() as session:
        artifact = session.scalars(select(AuditArtifact).where(AuditArtifact.deleted_at.is_(None))).first()
        assert artifact is not None
        durable_executor.artifact_cleanup_job_service.execute(session, [artifact.id])
        session.commit()

    with container.session_factory() as session:
        artifact = session.get(AuditArtifact, artifact.id)
        assert artifact is not None
        assert artifact.deleted_at is not None


def test_compaction_job_service_creates_summary_memory(client, auth_headers, default_cocoon_id):
    container = client.app.state.container
    durable_executor = _build_durable_executor(container)
    client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "first compaction source", "client_request_id": "compact-svc-1", "timezone": "UTC"},
    )
    client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "second compaction source", "client_request_id": "compact-svc-2", "timezone": "UTC"},
    )
    runtime = _build_worker_runtime(container)
    while runtime.process_next_chat_dispatch():
        pass

    with container.session_factory() as session:
        durable_executor.compaction_job_service.execute(session, default_cocoon_id)
        session.commit()
        summary = session.scalars(
            select(MemoryChunk).where(MemoryChunk.cocoon_id == default_cocoon_id, MemoryChunk.scope == "summary")
        ).first()
        assert summary is not None


def test_rollback_job_service_restores_checkpoint_anchor(client, auth_headers, default_cocoon_id):
    container = client.app.state.container
    durable_executor = _build_durable_executor(container)
    runtime = _build_worker_runtime(container)

    client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "rollback first", "client_request_id": "rollback-svc-1", "timezone": "UTC"},
    )
    assert runtime.process_next_chat_dispatch() is True

    with container.session_factory() as session:
        anchor = session.scalars(
            select(Message).where(Message.cocoon_id == default_cocoon_id).order_by(Message.created_at.desc())
        ).first()
        checkpoint = Checkpoint(cocoon_id=default_cocoon_id, anchor_message_id=anchor.id, label="svc-checkpoint")
        session.add(checkpoint)
        session.commit()
        checkpoint_id = checkpoint.id

    client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "rollback second", "client_request_id": "rollback-svc-2", "timezone": "UTC"},
    )
    assert runtime.process_next_chat_dispatch() is True

    with container.session_factory() as session:
        durable_executor.rollback_job_service.execute(session, checkpoint_id)
        session.commit()
        checkpoint = session.get(Checkpoint, checkpoint_id)
        assert checkpoint is not None and checkpoint.is_active is True


def test_runtime_job_service_marks_wakeup_complete(client, default_cocoon_id):
    container = client.app.state.container
    durable_executor = _build_durable_executor(container)
    with container.session_factory() as session:
        task, job = container.scheduler_node.schedule_wakeup(
            session,
            default_cocoon_id,
            run_at=datetime.now(UTC).replace(tzinfo=None),
            reason="svc wakeup",
            payload_json={},
        )
        session.commit()
        job_id = job.id

    with container.session_factory() as session:
        job = session.get(DurableJob, job_id)
        durable_executor.runtime_job_service.execute_wakeup(session, job)
        session.commit()
        task = session.get(WakeupTask, job.payload_json["wakeup_task_id"])
        assert task is not None
        assert task.status == "completed"
