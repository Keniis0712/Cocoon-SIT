from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DurableJob, SessionState, WakeupTask
from app.models.entities import DurableJobStatus
from app.services.workspace.targets import get_session_state


def list_pending_wakeup_tasks(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> list[WakeupTask]:
    query = select(WakeupTask).where(WakeupTask.status == DurableJobStatus.queued)
    if cocoon_id:
        query = query.where(WakeupTask.cocoon_id == cocoon_id, WakeupTask.chat_group_id.is_(None))
    if chat_group_id:
        query = query.where(WakeupTask.chat_group_id == chat_group_id, WakeupTask.cocoon_id.is_(None))
    return list(session.scalars(query.order_by(WakeupTask.run_at.asc(), WakeupTask.created_at.asc())).all())


def sync_current_wakeup_task_id(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
) -> SessionState | None:
    state = get_session_state(session, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    if not state:
        return None
    pending = list_pending_wakeup_tasks(session, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    state.current_wakeup_task_id = pending[0].id if pending else None
    session.flush()
    return state


def cancel_wakeup_tasks(
    session: Session,
    *,
    cocoon_id: str | None = None,
    chat_group_id: str | None = None,
    wakeup_task_ids: list[str] | None = None,
    only_trigger_kind: str | None = None,
    cancelled_reason: str | None = None,
) -> list[WakeupTask]:
    candidates = list_pending_wakeup_tasks(session, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    cancelled_at = datetime.now(UTC).replace(tzinfo=None)
    cancelled: list[WakeupTask] = []
    for task in candidates:
        if wakeup_task_ids is not None and task.id not in wakeup_task_ids:
            continue
        trigger_kind = str(task.payload_json.get("trigger_kind") or "")
        if only_trigger_kind and trigger_kind != only_trigger_kind:
            continue
        task.status = DurableJobStatus.cancelled
        task.cancelled_at = cancelled_at
        task.payload_json = {
            **task.payload_json,
            "cancelled_reason": cancelled_reason,
        }
        durable_job_id = task.payload_json.get("durable_job_id")
        if durable_job_id:
            job = session.get(DurableJob, durable_job_id)
            if job and job.status == DurableJobStatus.queued:
                job.status = DurableJobStatus.cancelled
                job.finished_at = cancelled_at
                job.error_text = cancelled_reason
        cancelled.append(task)
    sync_current_wakeup_task_id(session, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
    return cancelled
