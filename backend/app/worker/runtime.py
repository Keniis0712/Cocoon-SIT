from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.services.jobs.chat_dispatch import ChatDispatchQueue
from app.services.jobs.durable_jobs import DurableJobService
from app.services.realtime.hub import RealtimeHub
from app.services.runtime.orchestration.chat_runtime import ChatRuntime
from app.worker.chat_dispatch_worker_service import ChatDispatchWorkerService
from app.worker.durable_executor import DurableJobExecutor
from app.worker.durable_job_worker_service import DurableJobWorkerService


class WorkerRuntime:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        chat_queue: ChatDispatchQueue,
        chat_runtime: ChatRuntime,
        durable_jobs: DurableJobService,
        durable_executor: DurableJobExecutor,
        realtime_hub: RealtimeHub,
        worker_name: str,
    ) -> None:
        self.chat_dispatch_worker_service = ChatDispatchWorkerService(
            session_factory=session_factory,
            chat_queue=chat_queue,
            chat_runtime=chat_runtime,
            realtime_hub=realtime_hub,
        )
        self.durable_job_worker_service = DurableJobWorkerService(
            session_factory=session_factory,
            durable_jobs=durable_jobs,
            durable_executor=durable_executor,
            realtime_hub=realtime_hub,
            worker_name=worker_name,
        )

    def process_next_chat_dispatch(self) -> bool:
        return self.chat_dispatch_worker_service.process_next()

    def process_next_durable_job(self) -> bool:
        return self.durable_job_worker_service.process_next()
