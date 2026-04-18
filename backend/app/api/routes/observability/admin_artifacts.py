from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_db, require_permission
from app.core.container import AppContainer
from app.models.entities import DurableJobType
from app.schemas.observability.artifacts import ArtifactCleanupRequest
from app.schemas.observability.audits import AuditArtifactOut
from app.schemas.workspace.jobs import DurableJobOut

router = APIRouter()


@router.get("", response_model=list[AuditArtifactOut])
def list_artifacts(
    db: Session = Depends(get_db),
    _=Depends(require_permission("artifacts:cleanup")),
) -> list[AuditArtifactOut]:
    return db.info["container"].artifact_admin_service.list_artifacts(db)


@router.post("/cleanup", response_model=DurableJobOut)
def cleanup_artifacts(
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("artifacts:cleanup")),
) -> DurableJobOut:
    return container.durable_jobs.enqueue(
        session=db,
        job_type=DurableJobType.artifact_cleanup,
        lock_key="audit:artifacts:cleanup:expired",
        payload_json={"mode": "expired"},
        cocoon_id=None,
    )


@router.post("/cleanup/manual", response_model=DurableJobOut)
def manual_cleanup_artifacts(
    payload: ArtifactCleanupRequest,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("artifacts:cleanup")),
) -> DurableJobOut:
    return container.durable_jobs.enqueue(
        session=db,
        job_type=DurableJobType.artifact_cleanup,
        lock_key="audit:artifacts:cleanup:manual",
        payload_json={"mode": "manual", "artifact_ids": payload.artifact_ids},
        cocoon_id=None,
    )
