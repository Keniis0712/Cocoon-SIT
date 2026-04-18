from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import DurableJob, SessionState, WakeupTask
from app.models.entities import DurableJobStatus, DurableJobType
from app.services.jobs.durable_jobs import DurableJobService
from app.services.runtime.types import ContextPackage, MetaDecision


class SchedulerNode:
    """Schedules future wakeups and keeps session wakeup pointers in sync."""

    def __init__(self, durable_jobs: DurableJobService) -> None:
        self.durable_jobs = durable_jobs

    def _resolve_run_at(self, hint: dict[str, Any]) -> datetime:
        if run_at := hint.get("run_at"):
            if isinstance(run_at, datetime):
                return run_at.astimezone(UTC).replace(tzinfo=None) if run_at.tzinfo else run_at
            parsed = datetime.fromisoformat(str(run_at))
            return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed

        now = datetime.now(UTC).replace(tzinfo=None)
        if delay_seconds := hint.get("delay_seconds"):
            return now + timedelta(seconds=int(delay_seconds))
        if delay_minutes := hint.get("delay_minutes"):
            return now + timedelta(minutes=int(delay_minutes))
        if delay_hours := hint.get("delay_hours"):
            return now + timedelta(hours=int(delay_hours))
        raise ValueError("next_wakeup_hint must define run_at or a delay")

    def _ensure_session_state(self, session: Session, cocoon_id: str) -> SessionState:
        state = session.get(SessionState, cocoon_id)
        if state:
            return state
        state = SessionState(cocoon_id=cocoon_id, persona_json={}, active_tags_json=[])
        session.add(state)
        session.flush()
        return state

    def _job_for_task(self, session: Session, task: WakeupTask) -> DurableJob | None:
        durable_job_id = task.payload_json.get("durable_job_id")
        if not durable_job_id:
            return None
        return session.get(DurableJob, durable_job_id)

    def schedule_wakeup(
        self,
        session: Session,
        cocoon_id: str,
        run_at: datetime,
        *,
        reason: str | None,
        payload_json: dict[str, Any] | None = None,
    ) -> tuple[WakeupTask, DurableJob]:
        state = self._ensure_session_state(session, cocoon_id)
        payload = dict(payload_json or {})
        queued_task = (
            session.get(WakeupTask, state.current_wakeup_task_id)
            if state.current_wakeup_task_id
            else None
        )
        queued_job = self._job_for_task(session, queued_task) if queued_task else None
        if (
            queued_task
            and queued_task.status == DurableJobStatus.queued
            and queued_job
            and queued_job.status == DurableJobStatus.queued
        ):
            queued_task.run_at = run_at
            queued_task.reason = reason
            queued_job.available_at = run_at
            queued_job.payload_json = {"wakeup_task_id": queued_task.id}
            task = queued_task
            job = queued_job
        else:
            task = WakeupTask(
                cocoon_id=cocoon_id,
                run_at=run_at,
                reason=reason,
                payload_json={},
                status=DurableJobStatus.queued,
            )
            session.add(task)
            session.flush()
            job = self.durable_jobs.enqueue(
                session,
                job_type=DurableJobType.wakeup,
                lock_key=f"cocoon:{cocoon_id}:wakeup",
                payload_json={"wakeup_task_id": task.id},
                cocoon_id=cocoon_id,
                available_at=run_at,
            )

        task.payload_json = {
            **payload,
            "durable_job_id": job.id,
        }
        state.current_wakeup_task_id = task.id if run_at > datetime.now(UTC).replace(tzinfo=None) else None
        session.flush()
        return task, job

    def _schedule_compaction(
        self,
        session: Session,
        context: ContextPackage,
        *,
        reason: str,
    ) -> DurableJob | None:
        if not context.cocoon.auto_compaction_enabled or not context.visible_messages:
            return None
        return self.durable_jobs.enqueue(
            session,
            job_type=DurableJobType.compaction,
            lock_key=f"cocoon:{context.cocoon.id}:compaction",
            payload_json={
                "before_message_id": context.visible_messages[0].id,
                "reason": reason,
            },
            cocoon_id=context.cocoon.id,
        )

    def schedule(self, session: Session, context: ContextPackage, meta: MetaDecision) -> dict:
        result: dict[str, str | None] = {
            "wakeup_task_id": None,
            "wakeup_job_id": None,
            "compaction_job_id": None,
        }
        if meta.next_wakeup_hint:
            hint = dict(meta.next_wakeup_hint)
            run_at = self._resolve_run_at(hint)
            reason = str(hint.get("reason") or "Scheduled by meta node")
            payload_json = dict(hint.get("payload_json") or hint.get("payload") or {})
            payload_json.setdefault("scheduled_by", "meta_node")
            payload_json.setdefault("source_action_id", context.runtime_event.action_id)
            payload_json.setdefault("source_event_type", context.runtime_event.event_type)
            task, job = self.schedule_wakeup(
                session,
                context.cocoon.id,
                run_at,
                reason=reason,
                payload_json=payload_json,
            )
            result["wakeup_task_id"] = task.id
            result["wakeup_job_id"] = job.id
        if (
            len(context.visible_messages) >= context.cocoon.max_context_messages
            or context.runtime_event.event_type in {"pull", "merge"}
        ):
            reason = "post_sync_compaction" if context.runtime_event.event_type in {"pull", "merge"} else "window_limit"
            job = self._schedule_compaction(session, context, reason=reason)
            result["compaction_job_id"] = job.id if job else None
        return result
