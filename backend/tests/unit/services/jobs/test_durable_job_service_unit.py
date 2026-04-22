from datetime import UTC, datetime, timedelta

from app.models import DurableJob
from app.models.entities import DurableJobStatus
from app.services.jobs.durable_jobs import DurableJobService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_durable_job_service_enqueues_claims_and_finishes_jobs():
    session_factory = _session_factory()
    service = DurableJobService()
    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)

    with session_factory() as session:
        first = service.enqueue(
            session,
            "job-a",
            "lock-a",
            {"step": 1},
            cocoon_id="cocoon-1",
            available_at=past,
        )
        second = service.enqueue(
            session,
            "job-b",
            "lock-b",
            {"step": 2},
            chat_group_id="group-1",
            available_at=past,
        )
        claimed = service.claim_next(session, "worker-1")
        finished = service.finish(session, claimed, DurableJobStatus.completed, error_text=None)

        assert second.status == DurableJobStatus.queued
        assert claimed is not None
        assert claimed.id == first.id
        assert claimed.worker_name == "worker-1"
        assert claimed.started_at is not None
        assert finished.status == DurableJobStatus.completed
        assert finished.finished_at is not None


def test_durable_job_service_skips_future_jobs_and_handles_missing_claim():
    session_factory = _session_factory()
    service = DurableJobService()
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)

    with session_factory() as session:
        future_job = service.enqueue(session, "future-job", "lock-future", {}, available_at=future)
        running = DurableJob(
            job_type="running-job",
            lock_key="lock-running",
            payload_json={},
            status=DurableJobStatus.running,
            available_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(running)
        session.flush()

        assert service.claim_next(session, "worker-2") is None
        assert future_job.status == DurableJobStatus.queued
