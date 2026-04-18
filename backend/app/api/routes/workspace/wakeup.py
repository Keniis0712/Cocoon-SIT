from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_current_user, get_db, require_permission
from app.core.container import AppContainer
from app.models import WakeupTask
from app.schemas.workspace.jobs import WakeupEnqueueResult, WakeupRequest, WakeupTaskOut


router = APIRouter()

@router.post("", response_model=WakeupEnqueueResult)
def enqueue_wakeup(
    payload: WakeupRequest,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
    _=Depends(require_permission("wakeup:write")),
) -> WakeupEnqueueResult:
    container.authorization_service.require_cocoon_access(db, user, payload.cocoon_id, write=True)
    run_at = payload.run_at or datetime.now(UTC)
    if run_at.tzinfo:
        run_at = run_at.astimezone(UTC).replace(tzinfo=None)
    else:
        run_at = run_at.replace(tzinfo=None)
    task, job = container.scheduler_node.schedule_wakeup(
        db,
        payload.cocoon_id,
        run_at,
        reason=payload.reason,
        payload_json={"scheduled_by": "api"},
    )
    return WakeupEnqueueResult(task_id=task.id, job_id=job.id, status=job.status)


@router.get("", response_model=list[WakeupTaskOut])
def list_wakeup_tasks(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("wakeup:write")),
) -> list[WakeupTask]:
    tasks = list(db.scalars(select(WakeupTask).order_by(WakeupTask.run_at.asc())).all())
    visible = []
    for task in tasks:
        try:
            db.info["container"].authorization_service.require_cocoon_access(db, user, task.cocoon_id, write=False)
            visible.append(task)
        except HTTPException:
            continue
    return visible
