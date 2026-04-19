from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.enums import ActionStatus, DurableJobStatus
from app.models.identity import new_id, utcnow


class ActionDispatch(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "action_dispatches"
    __table_args__ = (
        CheckConstraint(
            "(cocoon_id IS NOT NULL AND chat_group_id IS NULL) OR (cocoon_id IS NULL AND chat_group_id IS NOT NULL)",
            name="ck_action_dispatches_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True)
    chat_group_id: Mapped[str | None] = mapped_column(ForeignKey("chat_group_rooms.id"), nullable=True)
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
    __table_args__ = (
        CheckConstraint(
            "NOT (cocoon_id IS NOT NULL AND chat_group_id IS NOT NULL)",
            name="ck_durable_jobs_single_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True)
    chat_group_id: Mapped[str | None] = mapped_column(ForeignKey("chat_group_rooms.id"), nullable=True)
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
    __table_args__ = (
        CheckConstraint(
            "(cocoon_id IS NOT NULL AND chat_group_id IS NULL) OR (cocoon_id IS NULL AND chat_group_id IS NOT NULL)",
            name="ck_wakeup_tasks_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True)
    chat_group_id: Mapped[str | None] = mapped_column(ForeignKey("chat_group_rooms.id"), nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    status: Mapped[str] = mapped_column(String(20), default=DurableJobStatus.queued)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    superseded_by_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("wakeup_tasks.id"),
        nullable=True,
    )


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
