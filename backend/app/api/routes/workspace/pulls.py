from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_current_user, get_db, require_permission
from app.core.container import AppContainer
from app.models import CocoonPullJob
from app.models.entities import DurableJobType
from app.schemas.workspace.jobs import PullEnqueueResult, PullJobOut, PullRequest


router = APIRouter()

@router.post("", response_model=PullEnqueueResult)
def enqueue_pull(
    payload: PullRequest,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
    _=Depends(require_permission("pulls:write")),
) -> PullEnqueueResult:
    container.authorization_service.require_pull_merge_access(
        db,
        user,
        source_cocoon_id=payload.source_cocoon_id,
        target_cocoon_id=payload.target_cocoon_id,
    )
    job = container.durable_jobs.enqueue(
        db,
        job_type=DurableJobType.pull,
        lock_key=f"cocoon:{payload.target_cocoon_id}:pull",
        payload_json=payload.model_dump(),
        cocoon_id=payload.target_cocoon_id,
    )
    pull_job = CocoonPullJob(
        durable_job_id=job.id,
        source_cocoon_id=payload.source_cocoon_id,
        target_cocoon_id=payload.target_cocoon_id,
    )
    db.add(pull_job)
    db.flush()
    return PullEnqueueResult(job_id=job.id, pull_job_id=pull_job.id, status=job.status)


@router.get("", response_model=list[PullJobOut])
def list_pulls(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("pulls:write")),
) -> list[CocoonPullJob]:
    items = list(db.scalars(select(CocoonPullJob).order_by(CocoonPullJob.created_at.desc())).all())
    visible: list[CocoonPullJob] = []
    for item in items:
        try:
            db.info["container"].authorization_service.require_pull_merge_access(
                db,
                user,
                source_cocoon_id=item.source_cocoon_id,
                target_cocoon_id=item.target_cocoon_id,
            )
            visible.append(item)
        except HTTPException:
            continue
    return visible
