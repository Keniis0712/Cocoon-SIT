from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.schemas.observability.audits import AuditRunDetail, AuditRunOut


router = APIRouter()


@router.get("", response_model=list[AuditRunOut])
def list_audits(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("audits:read")),
) -> list[AuditRunOut]:
    return db.info["container"].audit_query_service.list_runs(db, user)


@router.get("/{run_id}", response_model=AuditRunDetail)
def get_audit(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("audits:read")),
) -> AuditRunDetail:
    return db.info["container"].audit_query_service.get_run_detail(db, run_id, user)
