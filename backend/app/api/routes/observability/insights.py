from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import User
from app.schemas.observability.insights import InsightsDashboard, InsightsInterval, InsightsRange


router = APIRouter()


@router.get("/dashboard", response_model=InsightsDashboard)
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    range: InsightsRange = "30d",
    interval: InsightsInterval = "auto",
    _=Depends(require_permission("insights:read")),
) -> InsightsDashboard:
    return db.info["container"].insight_query_service.dashboard(
        db,
        user,
        range=range,
        interval=interval,
    )
