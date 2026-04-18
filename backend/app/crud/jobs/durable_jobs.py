from sqlalchemy.orm import Session

from app.models import DurableJob
from app.services.jobs.durable_jobs import DurableJobService


def enqueue_durable_job(
    session: Session,
    service: DurableJobService,
    job_type: str,
    lock_key: str,
    payload_json: dict,
    cocoon_id: str | None = None,
) -> DurableJob:
    return service.enqueue(session, job_type, lock_key, payload_json, cocoon_id)
