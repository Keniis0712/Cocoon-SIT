from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ChatGroupRoom, Cocoon, WakeupTask
from app.schemas.observability.wakeups import WakeupTaskOut
from app.services.runtime.scheduling.wakeup_tasks import is_ai_scheduled_wakeup


def serialize_wakeup_task(session: Session, task: WakeupTask) -> WakeupTaskOut:
    if task.chat_group_id:
        target_type = "chat_group"
        target_id = task.chat_group_id
        room = session.get(ChatGroupRoom, task.chat_group_id)
        target_name = room.name if room else None
    else:
        target_type = "cocoon"
        target_id = task.cocoon_id or ""
        cocoon = session.get(Cocoon, target_id) if target_id else None
        target_name = cocoon.name if cocoon else None

    payload = dict(task.payload_json or {})
    return WakeupTaskOut(
        id=task.id,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        run_at=task.run_at,
        reason=task.reason,
        status=task.status,
        scheduled_by=str(payload.get("scheduled_by") or "") or None,
        trigger_kind=str(payload.get("trigger_kind") or "") or None,
        is_ai_wakeup=is_ai_scheduled_wakeup(task),
        cancelled_at=task.cancelled_at,
        cancelled_reason=str(payload.get("cancelled_reason") or "") or None,
        created_at=task.created_at,
    )
