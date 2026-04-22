from datetime import datetime

from app.schemas.common import ORMModel


class WakeupTaskOut(ORMModel):
    id: str
    target_type: str
    target_id: str
    target_name: str | None = None
    run_at: datetime
    reason: str | None = None
    status: str
    scheduled_by: str | None = None
    trigger_kind: str | None = None
    is_ai_wakeup: bool
    cancelled_at: datetime | None = None
    cancelled_reason: str | None = None
    created_at: datetime
