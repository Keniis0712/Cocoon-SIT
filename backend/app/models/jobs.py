from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.enums import ActionStatus, DurableJobStatus
from app.models.identity import new_id, utcnow


class ActionDispatch(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "action_dispatches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ActionStatus.queued)
    client_request_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    debounce_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class DurableJob(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "durable_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=DurableJobStatus.queued)
    lock_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    worker_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class WakeupTask(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "wakeup_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    status: Mapped[str] = mapped_column(String(20), default=DurableJobStatus.queued)


class CocoonPullJob(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "cocoon_pull_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    durable_job_id: Mapped[str] = mapped_column(ForeignKey("durable_jobs.id"), nullable=False)
    source_cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    target_cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=DurableJobStatus.queued)
    summary_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class CocoonMergeJob(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "cocoon_merge_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    durable_job_id: Mapped[str] = mapped_column(ForeignKey("durable_jobs.id"), nullable=False)
    source_cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    target_cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=DurableJobStatus.queued)
    summary_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class Checkpoint(Base, TimestampMixin):
    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    anchor_message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
