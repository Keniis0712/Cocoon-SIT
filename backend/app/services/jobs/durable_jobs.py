"""Durable job service for asynchronous background work."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DurableJob
from app.models.entities import DurableJobStatus


class DurableJobService:
    """Enqueues, claims, and finishes durable jobs."""

    def enqueue(
        self,
        session: Session,
        job_type: str,
        lock_key: str,
        payload_json: dict,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        available_at: datetime | None = None,
    ) -> DurableJob:
        job = DurableJob(
            job_type=job_type,
            lock_key=lock_key,
            payload_json=payload_json,
            cocoon_id=cocoon_id,
            chat_group_id=chat_group_id,
            status=DurableJobStatus.queued,
            available_at=available_at or datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(job)
        session.flush()
        return job

    def claim_next(self, session: Session, worker_name: str) -> DurableJob | None:
        query = (
            select(DurableJob)
            .where(
                DurableJob.status == DurableJobStatus.queued,
                DurableJob.available_at <= datetime.now(UTC).replace(tzinfo=None),
            )
            .order_by(DurableJob.created_at.asc())
        )
        try:
            query = query.with_for_update(skip_locked=True)
        except Exception:
            pass
        job = session.scalars(query.limit(1)).first()
        if not job:
            return None
        job.status = DurableJobStatus.running
        job.started_at = datetime.now(UTC).replace(tzinfo=None)
        job.worker_name = worker_name
        session.flush()
        return job

    def finish(self, session: Session, job: DurableJob, status: str, error_text: str | None = None) -> DurableJob:
        job.status = status
        job.error_text = error_text
        job.finished_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()
        return job
