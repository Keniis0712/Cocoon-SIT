from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SystemSettingsUpdate(BaseModel):
    allow_registration: bool | None = None
    max_chat_turns: int | None = Field(default=None, ge=0)
    allowed_model_ids: list[str] | None = None
    default_cocoon_temperature: float | None = None
    default_max_context_messages: int | None = Field(default=None, ge=1)
    default_auto_compaction_enabled: bool | None = None
    private_chat_debounce_seconds: int | None = Field(default=None, ge=0)
    rollback_retention_days: int | None = Field(default=None, ge=0)
    rollback_cleanup_interval_hours: int | None = Field(default=None, ge=1)


class SystemSettingsOut(ORMModel):
    id: str
    allow_registration: bool
    max_chat_turns: int
    allowed_model_ids: list[str]
    default_cocoon_temperature: float
    default_max_context_messages: int
    default_auto_compaction_enabled: bool
    private_chat_debounce_seconds: int
    rollback_retention_days: int
    rollback_cleanup_interval_hours: int
    created_at: datetime
    updated_at: datetime
