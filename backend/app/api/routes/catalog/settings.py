from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import SystemSettings
from app.schemas.catalog.settings import SystemSettingsOut, SystemSettingsUpdate


router = APIRouter()


def _serialize(settings: SystemSettings) -> SystemSettingsOut:
    return SystemSettingsOut(
        id=settings.id,
        allow_registration=settings.allow_registration,
        max_chat_turns=settings.max_chat_turns,
        allowed_model_ids=settings.allowed_model_ids_json,
        default_max_context_messages=settings.default_max_context_messages,
        default_auto_compaction_enabled=settings.default_auto_compaction_enabled,
        private_chat_debounce_seconds=settings.private_chat_debounce_seconds,
        group_chat_debounce_seconds=settings.group_chat_debounce_seconds,
        rollback_retention_days=settings.rollback_retention_days,
        rollback_cleanup_interval_hours=settings.rollback_cleanup_interval_hours,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.get("", response_model=SystemSettingsOut)
def get_system_settings(
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings:read")),
) -> SystemSettingsOut:
    return _serialize(db.info["container"].system_settings_service.get_settings(db))


@router.put("", response_model=SystemSettingsOut)
def update_system_settings(
    payload: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings:write")),
) -> SystemSettingsOut:
    updated = db.info["container"].system_settings_service.update_settings(db, payload)
    return _serialize(updated)
