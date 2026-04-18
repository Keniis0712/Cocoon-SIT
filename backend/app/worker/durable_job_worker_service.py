from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.models import FailedRound
from app.models.entities import DurableJobStatus
from app.services.jobs.durable_jobs import DurableJobService
from app.services.realtime.hub import RealtimeHub
from app.worker.durable_executor import DurableJobExecutor


class DurableJobWorkerService:
    """Claims durable jobs, executes them, and publishes job status updates."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        durable_jobs: DurableJobService,
        durable_executor: DurableJobExecutor,
        realtime_hub: RealtimeHub,
        worker_name: str,
    ) -> None:
        self.session_factory = session_factory
        self.durable_jobs = durable_jobs
        self.durable_executor = durable_executor
        self.realtime_hub = realtime_hub
        self.worker_name = worker_name

    def process_next(self) -> bool:
        with self.session_factory() as session:
            job = self.durable_jobs.claim_next(session, self.worker_name)
            if not job:
                session.commit()
                return False
            self.realtime_hub.publish(
                job.cocoon_id or "global",
                {"type": "job_status", "action_id": job.id, "status": DurableJobStatus.running},
            )
            try:
                self.durable_executor.execute(session, job)
                self.durable_jobs.finish(session, job, DurableJobStatus.completed)
                self.realtime_hub.publish(
                    job.cocoon_id or "global",
                    {"type": "job_status", "action_id": job.id, "status": DurableJobStatus.completed},
                )
            except Exception as exc:  # noqa: BLE001
                if job.cocoon_id:
                    session.add(
                        FailedRound(
                            cocoon_id=job.cocoon_id,
                            action_id=None,
                            event_type=job.job_type,
                            reason=str(exc),
                        )
                    )
                self.durable_jobs.finish(session, job, DurableJobStatus.failed, str(exc))
                self.realtime_hub.publish(
                    job.cocoon_id or "global",
                    {"type": "error", "action_id": job.id, "reason": str(exc)},
                )
                session.commit()
                return True
            session.commit()
            return True
