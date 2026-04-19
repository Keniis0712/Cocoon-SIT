"""Runtime-oriented durable job execution service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CocoonMergeJob, CocoonPullJob, DurableJob, SessionState, WakeupTask
from app.models.entities import DurableJobStatus
from app.services.runtime.wakeup_tasks import sync_current_wakeup_task_id
from app.services.runtime.chat_runtime import ChatRuntime
from app.services.workspace.targets import get_session_state
from app.worker.jobs.runtime_action_service import RuntimeActionService


class RuntimeJobService:
    """Routes wakeup, pull, and merge durable jobs back through ChatRuntime."""

    def __init__(
        self,
        chat_runtime: ChatRuntime,
        runtime_action_service: RuntimeActionService,
    ) -> None:
        self.chat_runtime = chat_runtime
        self.runtime_action_service = runtime_action_service

    def execute_wakeup(self, session: Session, job: DurableJob) -> None:
        """Execute a wakeup durable job through the runtime."""
        task = session.get(WakeupTask, job.payload_json["wakeup_task_id"])
        if task and task.status == DurableJobStatus.cancelled:
            sync_current_wakeup_task_id(session, cocoon_id=job.cocoon_id, chat_group_id=job.chat_group_id)
            return
        if task:
            task.status = DurableJobStatus.running
            state = get_session_state(session, cocoon_id=task.cocoon_id, chat_group_id=task.chat_group_id)
            if state and state.current_wakeup_task_id == task.id:
                state.current_wakeup_task_id = None
        action = self.runtime_action_service.create_runtime_action(
            session,
            event_type="wakeup",
            payload_json={
                "wakeup_task_id": task.id if task else None,
                "reason": task.reason if task else None,
                **(task.payload_json if task else {}),
            },
            cocoon_id=job.cocoon_id,
            chat_group_id=job.chat_group_id,
        )
        self.chat_runtime.run(session, action)
        if task:
            task.status = DurableJobStatus.completed
        sync_current_wakeup_task_id(session, cocoon_id=job.cocoon_id, chat_group_id=job.chat_group_id)

    def execute_pull(self, session: Session, job: DurableJob) -> None:
        """Execute a pull durable job through the runtime."""
        pull_job = session.scalar(
            select(CocoonPullJob).where(CocoonPullJob.durable_job_id == job.id)
        )
        action = self.runtime_action_service.create_runtime_action(
            session,
            event_type="pull",
            payload_json=job.payload_json,
            cocoon_id=job.cocoon_id,
        )
        self.chat_runtime.run(session, action)
        if pull_job:
            pull_job.status = DurableJobStatus.completed
            pull_job.summary_json = {"action_id": action.id}

    def execute_merge(self, session: Session, job: DurableJob) -> None:
        """Execute a merge durable job through the runtime."""
        merge_job = session.scalar(
            select(CocoonMergeJob).where(CocoonMergeJob.durable_job_id == job.id)
        )
        action = self.runtime_action_service.create_runtime_action(
            session,
            event_type="merge",
            payload_json=job.payload_json,
            cocoon_id=job.cocoon_id,
        )
        self.chat_runtime.run(session, action)
        if merge_job:
            merge_job.status = DurableJobStatus.completed
            merge_job.summary_json = {"action_id": action.id}
