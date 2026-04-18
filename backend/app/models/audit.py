from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.enums import ActionStatus
from app.models.identity import new_id, utcnow


class AuditRun(Base, TimestampMixin):
    __tablename__ = "audit_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True)
    action_id: Mapped[str | None] = mapped_column(ForeignKey("action_dispatches.id"), nullable=True)
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ActionStatus.running)
    trigger_event_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class AuditStep(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "audit_steps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("audit_runs.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ActionStatus.running)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class AuditArtifact(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "audit_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("audit_runs.id"), nullable=False)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("audit_steps.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), default="filesystem")
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class AuditLink(Base, TimestampMixin):
    __tablename__ = "audit_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("audit_runs.id"), nullable=False)
    source_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("audit_artifacts.id"), nullable=True)
    source_step_id: Mapped[str | None] = mapped_column(ForeignKey("audit_steps.id"), nullable=True)
    target_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("audit_artifacts.id"), nullable=True)
    target_step_id: Mapped[str | None] = mapped_column(ForeignKey("audit_steps.id"), nullable=True)
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
