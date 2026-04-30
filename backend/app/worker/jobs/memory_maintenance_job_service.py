"""Background cleanup and decay routines for long-term memory."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import MemoryCandidate, MemoryChunk, SystemSettings


class MemoryMaintenanceJobService:
    """Applies candidate cleanup, decay, and archival rules."""

    def execute(self, session: Session) -> None:
        settings = session.get(SystemSettings, "default")
        profiles = (settings.memory_profiles_json or {}) if settings else {}
        baseline = profiles.get("meta_reply") or {}
        decay_days = int(baseline.get("maintenance_decay_days") or 90)
        archive_after_days = int(baseline.get("archive_after_days") or 180)
        cutoff_decay = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=decay_days)
        cutoff_archive = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=archive_after_days)
        for candidate in session.scalars(
            select(MemoryCandidate).where(
                MemoryCandidate.valid_until.is_not(None),
                MemoryCandidate.valid_until < datetime.now(UTC).replace(tzinfo=None),
            )
        ).all():
            session.delete(candidate)
        for memory in session.scalars(
            select(MemoryChunk).where(
                MemoryChunk.status == "active",
                or_(
                    MemoryChunk.last_accessed_at.is_(None),
                    MemoryChunk.last_accessed_at < cutoff_decay,
                ),
            )
        ).all():
            if int(memory.importance or 0) > 0:
                memory.importance = max(0, int(memory.importance) - 1)
            if (memory.last_accessed_at or memory.updated_at or memory.created_at) < cutoff_archive:
                memory.status = "archived"
        session.flush()
