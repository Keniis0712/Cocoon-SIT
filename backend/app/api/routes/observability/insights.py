from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_db, require_permission
from app.models import User
from app.schemas.observability.insights import InsightsSummary


router = APIRouter()


@router.get("/summary", response_model=InsightsSummary)
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("insights:read")),
) -> InsightsSummary:
    return db.info["container"].insight_query_service.summary(db, user)
