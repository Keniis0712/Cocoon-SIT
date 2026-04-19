from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import DurableJob, WakeupTask
from app.models.entities import DurableJobStatus, DurableJobType
from app.services.jobs.durable_jobs import DurableJobService
from app.services.runtime.types import ContextPackage, MetaDecision
from app.services.runtime.wakeup_tasks import cancel_wakeup_tasks, list_pending_wakeup_tasks, sync_current_wakeup_task_id
from app.services.workspace.targets import resolve_target_type


class SchedulerNode:
    """Schedules future wakeups and keeps session wakeup pointers in sync."""

    DEFAULT_IDLE_WAKEUP_DELAY_SECONDS = 5 * 60
    FREQUENT_COCOON_IDLE_WAKEUP_DELAY_SECONDS = 2 * 60

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
        raise ValueError("wakeup hint must define run_at or a delay")

    def _job_for_task(self, session: Session, task: WakeupTask) -> DurableJob | None:
        durable_job_id = task.payload_json.get("durable_job_id")
        if not durable_job_id:
            return None
        return session.get(DurableJob, durable_job_id)

    def schedule_wakeup(
        self,
        session: Session,
        *args,
        run_at: datetime | None = None,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        reason: str | None,
        payload_json: dict[str, Any] | None = None,
    ) -> tuple[WakeupTask, DurableJob]:
        if args:
            if len(args) == 1:
                if isinstance(args[0], datetime):
                    if run_at is not None:
                        raise TypeError("schedule_wakeup() got multiple values for argument 'run_at'")
                    run_at = args[0]
                else:
                    if cocoon_id is not None or chat_group_id is not None:
                        raise TypeError("schedule_wakeup() got multiple target identifiers")
                    cocoon_id = args[0]
            elif len(args) == 2:
                if run_at is not None or cocoon_id is not None or chat_group_id is not None:
                    raise TypeError("schedule_wakeup() got conflicting legacy and keyword arguments")
                cocoon_id = args[0]
                run_at = args[1]
            else:
                raise TypeError("schedule_wakeup() accepts at most two positional arguments after session")
        if run_at is None:
            raise TypeError("schedule_wakeup() missing required run_at")
        if run_at.tzinfo:
            run_at = run_at.astimezone(UTC).replace(tzinfo=None)
        if not reason or not str(reason).strip():
            raise ValueError("schedule_wakeup() requires a non-empty reason")
        payload = dict(payload_json or {})
        task = WakeupTask(
            cocoon_id=cocoon_id,
            chat_group_id=chat_group_id,
            run_at=run_at,
            reason=str(reason).strip(),
            payload_json={},
            status=DurableJobStatus.queued,
        )
        session.add(task)
        session.flush()
        target_type, target_id = resolve_target_type(cocoon_id=cocoon_id, chat_group_id=chat_group_id)
        job = self.durable_jobs.enqueue(
            session,
            job_type=DurableJobType.wakeup,
            lock_key=f"{'chat-group' if target_type == 'chat_group' else 'cocoon'}:{target_id}:wakeup:{task.id}",
            payload_json={"wakeup_task_id": task.id},
            cocoon_id=cocoon_id,
            chat_group_id=chat_group_id,
            available_at=run_at,
        )

        task.payload_json = {
            **payload,
            "durable_job_id": job.id,
        }
        sync_current_wakeup_task_id(session, cocoon_id=cocoon_id, chat_group_id=chat_group_id)
        return task, job

    def _schedule_compaction(
        self,
        session: Session,
        context: ContextPackage,
        *,
        reason: str,
    ) -> DurableJob | None:
        if context.target_type != "cocoon":
            return None
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
        result: dict[str, str | list[str] | None] = {
            "wakeup_task_id": None,
            "wakeup_job_id": None,
            "wakeup_task_ids": [],
            "wakeup_job_ids": [],
            "cancelled_wakeup_task_ids": [],
            "compaction_job_id": None,
        }
        if meta.cancel_wakeup_task_ids:
            cancelled = cancel_wakeup_tasks(
                session,
                cocoon_id=context.runtime_event.cocoon_id,
                chat_group_id=context.runtime_event.chat_group_id,
                wakeup_task_ids=meta.cancel_wakeup_task_ids,
                cancelled_reason=f"Cancelled by meta node during action {context.runtime_event.action_id}",
            )
            result["cancelled_wakeup_task_ids"] = [task.id for task in cancelled]
        for hint_payload in meta.next_wakeup_hints:
            hint = dict(hint_payload)
            run_at = self._resolve_run_at(hint)
            reason = str(hint.get("reason") or "").strip()
            payload_json = dict(hint.get("payload_json") or hint.get("payload") or {})
            payload_json.setdefault("scheduled_by", "meta_node")
            payload_json.setdefault("source_action_id", context.runtime_event.action_id)
            payload_json.setdefault("source_event_type", context.runtime_event.event_type)
            if context.memory_owner_user_id:
                payload_json.setdefault("memory_owner_user_id", context.memory_owner_user_id)
            task, job = self.schedule_wakeup(
                session,
                run_at,
                cocoon_id=context.runtime_event.cocoon_id,
                chat_group_id=context.runtime_event.chat_group_id,
                reason=reason or "Scheduled by meta node",
                payload_json=payload_json,
            )
            if result["wakeup_task_id"] is None:
                result["wakeup_task_id"] = task.id
                result["wakeup_job_id"] = job.id
            result["wakeup_task_ids"].append(task.id)
            result["wakeup_job_ids"].append(job.id)
        if self._should_schedule_idle_wakeup(session, context, meta):
            task, job = self._schedule_idle_wakeup(session, context)
            if result["wakeup_task_id"] is None:
                result["wakeup_task_id"] = task.id
                result["wakeup_job_id"] = job.id
            result["wakeup_task_ids"].append(task.id)
            result["wakeup_job_ids"].append(job.id)
        if context.target_type == "cocoon" and (
            len(context.visible_messages) >= context.cocoon.max_context_messages
            or context.runtime_event.event_type in {"pull", "merge"}
        ):
            reason = "post_sync_compaction" if context.runtime_event.event_type in {"pull", "merge"} else "window_limit"
            job = self._schedule_compaction(session, context, reason=reason)
            result["compaction_job_id"] = job.id if job else None
        sync_current_wakeup_task_id(
            session,
            cocoon_id=context.runtime_event.cocoon_id,
            chat_group_id=context.runtime_event.chat_group_id,
        )
        return result

    def _should_schedule_idle_wakeup(
        self,
        session: Session,
        context: ContextPackage,
        meta: MetaDecision,
    ) -> bool:
        if context.runtime_event.event_type != "chat":
            return False
        if meta.next_wakeup_hints:
            return False
        pending = list_pending_wakeup_tasks(
            session,
            cocoon_id=context.runtime_event.cocoon_id,
            chat_group_id=context.runtime_event.chat_group_id,
        )
        if pending:
            return False
        return True

    def _schedule_idle_wakeup(self, session: Session, context: ContextPackage) -> tuple[WakeupTask, DurableJob]:
        silence_started_at = datetime.now(UTC).replace(tzinfo=None)
        delay_seconds = self._resolve_idle_wakeup_delay_seconds(context)
        run_at = silence_started_at + timedelta(seconds=delay_seconds)
        delay_minutes = int(delay_seconds / 60)
        reason = (
            f"The conversation has been quiet since {silence_started_at.isoformat()} UTC; "
            f"check back after about {delay_minutes} minute(s)."
        )
        payload_json = {
            "scheduled_by": "idle_timeout_default",
            "trigger_kind": "idle_timeout",
            "source_action_id": context.runtime_event.action_id,
            "source_event_type": context.runtime_event.event_type,
            "silence_started_at": silence_started_at.isoformat(),
            "silence_delay_seconds": delay_seconds,
            "silence_deadline_at": run_at.isoformat(),
            "idle_summary": (
                f"The conversation stopped at {silence_started_at.isoformat()} UTC and has been idle "
                f"for about {delay_minutes} minute(s)."
            ),
        }
        if context.memory_owner_user_id:
            payload_json["memory_owner_user_id"] = context.memory_owner_user_id
        return self.schedule_wakeup(
            session,
            run_at,
            cocoon_id=context.runtime_event.cocoon_id,
            chat_group_id=context.runtime_event.chat_group_id,
            reason=reason,
            payload_json=payload_json,
        )

    def _resolve_idle_wakeup_delay_seconds(self, context: ContextPackage) -> int:
        if context.target_type != "cocoon":
            return self.DEFAULT_IDLE_WAKEUP_DELAY_SECONDS
        payload = context.runtime_event.payload
        recent_turn_count = payload.get("recent_turn_count")
        idle_seconds = payload.get("idle_seconds")
        try:
            if recent_turn_count is not None and int(recent_turn_count) >= 3:
                return self.FREQUENT_COCOON_IDLE_WAKEUP_DELAY_SECONDS
        except (TypeError, ValueError):
            pass
        try:
            if idle_seconds is not None and int(idle_seconds) <= 120:
                return self.FREQUENT_COCOON_IDLE_WAKEUP_DELAY_SECONDS
        except (TypeError, ValueError):
            pass
        recent_dialogue_messages = [
            message
            for message in context.visible_messages
            if message.role in {"user", "assistant"} and not message.is_retracted
        ][-6:]
        if len(recent_dialogue_messages) >= 4:
            oldest = recent_dialogue_messages[0].created_at
            newest = recent_dialogue_messages[-1].created_at
            if oldest and newest and (newest - oldest) <= timedelta(minutes=15):
                return self.FREQUENT_COCOON_IDLE_WAKEUP_DELAY_SECONDS
        return self.DEFAULT_IDLE_WAKEUP_DELAY_SECONDS
