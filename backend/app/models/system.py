from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin


class SystemSettings(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    allow_registration: Mapped[bool] = mapped_column(Boolean, default=False)
    max_chat_turns: Mapped[int] = mapped_column(Integer, default=0)
    allowed_model_ids_json: Mapped[list[str]] = mapped_column(JSON, default=JsonDefaultMixin.json_list)
    default_cocoon_temperature: Mapped[float] = mapped_column(Float, default=0.7)
    default_max_context_messages: Mapped[int] = mapped_column(Integer, default=12)
    default_auto_compaction_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    private_chat_debounce_seconds: Mapped[int] = mapped_column(Integer, default=2)
    rollback_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    rollback_cleanup_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
