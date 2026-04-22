from types import SimpleNamespace

from app.models import DurableJob, FailedRound
from app.services.jobs.durable_jobs import DurableJobService
from app.worker.durable_job_worker_service import DurableJobWorkerService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


class _RealtimeHub:
    def __init__(self):
        self.published = []

    def publish(self, channel, payload):
        self.published.append((channel, payload))


def test_durable_job_worker_service_returns_false_when_no_job_is_available():
    session_factory = _session_factory()
    realtime_hub = _RealtimeHub()
    worker = DurableJobWorkerService(
        session_factory=session_factory,
        durable_jobs=DurableJobService(),
        durable_executor=SimpleNamespace(execute=lambda session, job: None),
        realtime_hub=realtime_hub,
        worker_name="worker-1",
    )

    assert worker.process_next() is False
    assert realtime_hub.published == []


def test_durable_job_worker_service_processes_successful_jobs_and_publishes_updates():
    session_factory = _session_factory()
    durable_jobs = DurableJobService()
    realtime_hub = _RealtimeHub()
    seen = []

    with session_factory() as session:
        job = durable_jobs.enqueue(
            session,
            job_type="merge",
            lock_key="job-success",
            payload_json={},
            cocoon_id="cocoon-1",
        )
        session.commit()
        job_id = job.id

    worker = DurableJobWorkerService(
        session_factory=session_factory,
        durable_jobs=durable_jobs,
        durable_executor=SimpleNamespace(execute=lambda session, job: seen.append(job.id)),
        realtime_hub=realtime_hub,
        worker_name="worker-1",
    )

    assert worker.process_next() is True
    assert seen == [job_id]
    assert realtime_hub.published == [
        ("cocoon-1", {"type": "job_status", "action_id": job_id, "status": "running"}),
        ("cocoon-1", {"type": "job_status", "action_id": job_id, "status": "completed"}),
    ]

    with session_factory() as session:
        persisted = session.get(DurableJob, job_id)
        assert persisted is not None
        assert persisted.status == "completed"
        assert persisted.worker_name == "worker-1"


def test_durable_job_worker_service_records_failed_rounds_and_global_errors():
    session_factory = _session_factory()
    durable_jobs = DurableJobService()

    with session_factory() as session:
        cocoon_job = durable_jobs.enqueue(
            session,
            job_type="wakeup",
            lock_key="job-fail-cocoon",
            payload_json={},
            cocoon_id="cocoon-1",
        )
        global_job = durable_jobs.enqueue(
            session,
            job_type="artifact_cleanup",
            lock_key="job-fail-global",
            payload_json={},
            cocoon_id=None,
        )
        session.commit()
        cocoon_job_id = cocoon_job.id
        global_job_id = global_job.id

    realtime_hub = _RealtimeHub()

    def _boom(session, job):
        raise ValueError(f"boom-{job.id}")

    worker = DurableJobWorkerService(
        session_factory=session_factory,
        durable_jobs=durable_jobs,
        durable_executor=SimpleNamespace(execute=_boom),
        realtime_hub=realtime_hub,
        worker_name="worker-1",
    )

    assert worker.process_next() is True
    assert worker.process_next() is True

    with session_factory() as session:
        failed_cocoon_job = session.get(DurableJob, cocoon_job_id)
        failed_global_job = session.get(DurableJob, global_job_id)
        failed_rounds = list(session.query(FailedRound).all())

        assert failed_cocoon_job is not None and failed_cocoon_job.status == "failed"
        assert failed_global_job is not None and failed_global_job.status == "failed"
        assert len(failed_rounds) == 1
        assert failed_rounds[0].cocoon_id == "cocoon-1"
        assert failed_rounds[0].reason == f"boom-{cocoon_job_id}"

    assert realtime_hub.published == [
        ("cocoon-1", {"type": "job_status", "action_id": cocoon_job_id, "status": "running"}),
        ("cocoon-1", {"type": "error", "action_id": cocoon_job_id, "reason": f"boom-{cocoon_job_id}"}),
        ("global", {"type": "job_status", "action_id": global_job_id, "status": "running"}),
        ("global", {"type": "error", "action_id": global_job_id, "reason": f"boom-{global_job_id}"}),
    ]
