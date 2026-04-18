from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_current_user, get_db, require_permission
from app.core.container import AppContainer
from app.models import CocoonMergeJob
from app.models.entities import DurableJobType
from app.schemas.workspace.jobs import MergeEnqueueResult, MergeJobOut, MergeRequest


router = APIRouter()

@router.post("", response_model=MergeEnqueueResult)
def enqueue_merge(
    payload: MergeRequest,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
    _=Depends(require_permission("merges:write")),
) -> MergeEnqueueResult:
    container.authorization_service.require_pull_merge_access(
        db,
        user,
        source_cocoon_id=payload.source_cocoon_id,
        target_cocoon_id=payload.target_cocoon_id,
    )
    job = container.durable_jobs.enqueue(
        db,
        job_type=DurableJobType.merge,
        lock_key=f"cocoon:{payload.target_cocoon_id}:merge",
        payload_json=payload.model_dump(),
        cocoon_id=payload.target_cocoon_id,
    )
    merge_job = CocoonMergeJob(
        durable_job_id=job.id,
        source_cocoon_id=payload.source_cocoon_id,
        target_cocoon_id=payload.target_cocoon_id,
    )
    db.add(merge_job)
    db.flush()
    return MergeEnqueueResult(job_id=job.id, merge_job_id=merge_job.id, status=job.status)


@router.get("", response_model=list[MergeJobOut])
def list_merges(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("merges:write")),
) -> list[CocoonMergeJob]:
    items = list(db.scalars(select(CocoonMergeJob).order_by(CocoonMergeJob.created_at.desc())).all())
    visible: list[CocoonMergeJob] = []
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
