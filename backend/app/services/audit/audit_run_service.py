from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import ActionDispatch, AuditRun, AuditStep
from app.models.entities import ActionStatus


class AuditRunService:
    """Creates and finalizes audit runs and steps."""

    def start_run(
        self,
        session: Session,
        cocoon_id: str | None,
        chat_group_id: str | None,
        action: ActionDispatch | None,
        operation_type: str,
    ) -> AuditRun:
        run = AuditRun(
            cocoon_id=cocoon_id,
            chat_group_id=chat_group_id,
            action_id=action.id if action else None,
            operation_type=operation_type,
            status=ActionStatus.running,
            trigger_event_uid=action.id if action else None,
        )
        session.add(run)
        session.flush()
        return run

    def finish_run(self, session: Session, run: AuditRun, status: str) -> AuditRun:
        run.status = status
        run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()
        return run

    def start_step(
        self,
        session: Session,
        run: AuditRun,
        step_name: str,
        meta_json: dict | None = None,
    ) -> AuditStep:
        step = AuditStep(run_id=run.id, step_name=step_name, meta_json=meta_json or {})
        session.add(step)
        session.flush()
        return step

    def finish_step(self, session: Session, step: AuditStep, status: str) -> AuditStep:
        step.status = status
        step.finished_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()
        return step
