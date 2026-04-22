from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.api.wakeup_serialization import serialize_wakeup_task
from app.schemas.observability.wakeups import WakeupTaskOut
from app.services.runtime.wakeup_tasks import list_wakeup_tasks


router = APIRouter()


@router.get("", response_model=list[WakeupTaskOut])
def list_wakeups(
    status: str | None = Query(default=None),
    target_type: Literal["cocoon", "chat_group"] | None = Query(default=None),
    target_id: str | None = Query(default=None),
    only_ai: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("audits:read")),
) -> list[WakeupTaskOut]:
    cocoon_id = target_id if target_type == "cocoon" else None
    chat_group_id = target_id if target_type == "chat_group" else None
    tasks = list_wakeup_tasks(
        db,
        cocoon_id=cocoon_id,
        chat_group_id=chat_group_id,
        status=status,
        only_ai=only_ai,
        limit=limit,
    )
    return [serialize_wakeup_task(db, task) for task in tasks]
