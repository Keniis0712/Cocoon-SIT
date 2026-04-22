from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import ActionDispatch, DurableJob, Message, WakeupTask
from app.worker.chat_dispatch_worker_service import ChatDispatchWorkerService
from app.worker.durable_executor import DurableJobExecutor
from app.worker.durable_job_worker_service import DurableJobWorkerService

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


def test_chat_dispatch_worker_service_processes_queued_message(client, auth_headers, default_cocoon_id):
    container = client.app.state.container
    worker = ChatDispatchWorkerService(
        session_factory=container.session_factory,
        chat_queue=container.chat_queue,
        chat_runtime=container.chat_runtime,
    )
    client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "worker service message", "client_request_id": "worker-svc-1", "timezone": "UTC"},
    )

    assert worker.process_next() is True

    with container.session_factory() as session:
        action = session.scalars(select(ActionDispatch).where(ActionDispatch.client_request_id == "worker-svc-1")).first()
        message = session.scalars(
            select(Message).where(Message.cocoon_id == default_cocoon_id, Message.role == "assistant")
        ).first()
        assert action is not None
        assert action.status == "completed"
        assert message is not None


def test_durable_job_worker_service_processes_wakeup_job(client, default_cocoon_id):
    container = client.app.state.container
    worker = DurableJobWorkerService(
        session_factory=container.session_factory,
        durable_jobs=container.durable_jobs,
        durable_executor=_build_durable_executor(container),
        realtime_hub=container.realtime_hub,
        worker_name=container.settings.durable_job_worker_name,
    )

    with container.session_factory() as session:
        task, job = container.scheduler_node.schedule_wakeup(
            session,
            default_cocoon_id,
            run_at=datetime.now(UTC).replace(tzinfo=None),
            reason="worker service wakeup",
            payload_json={},
        )
        session.commit()
        job_id = job.id
        task_id = task.id

    assert worker.process_next() is True

    with container.session_factory() as session:
        job = session.get(DurableJob, job_id)
        task = session.get(WakeupTask, task_id)
        action = session.scalars(
            select(ActionDispatch).where(
                ActionDispatch.cocoon_id == default_cocoon_id,
                ActionDispatch.event_type == "wakeup",
            )
        ).first()
        assert job is not None
        assert job.status == "completed"
        assert task is not None
        assert task.status == "completed"
        assert action is not None
