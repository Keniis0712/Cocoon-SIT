from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_current_user, get_db, require_permission
from app.core.container import AppContainer
from app.models.entities import DurableJobType
from app.schemas.workspace.cocoons import RollbackRequest
from app.schemas.workspace.jobs import DurableJobOut


router = APIRouter()


@router.post("/{cocoon_id}/rollback", response_model=DurableJobOut)
def request_rollback(
    cocoon_id: str,
    payload: RollbackRequest,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
    _=Depends(require_permission("checkpoints:write")),
):
    container.authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    job = container.durable_jobs.enqueue(
        session=db,
        job_type=DurableJobType.rollback,
        lock_key=f"cocoon:{cocoon_id}:rollback",
        payload_json={"checkpoint_id": payload.checkpoint_id},
        cocoon_id=cocoon_id,
    )
    return job
