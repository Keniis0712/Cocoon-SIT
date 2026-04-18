from __future__ import annotations

from app.core.config import Settings
from app.core.container import AppContainer
from app.worker.durable_executor import DurableJobExecutor
from app.worker.runtime import WorkerRuntime


class WorkerContainer(AppContainer):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.durable_executor = DurableJobExecutor(
            chat_runtime=self.chat_runtime,
            durable_jobs=self.durable_jobs,
            audit_service=self.audit_service,
            round_cleanup=self.round_cleanup,
            prompt_service=self.prompt_service,
            provider_registry=self.provider_registry,
        )
        self.worker_runtime = WorkerRuntime(
            session_factory=self.session_factory,
            chat_queue=self.chat_queue,
            chat_runtime=self.chat_runtime,
            durable_jobs=self.durable_jobs,
            durable_executor=self.durable_executor,
            realtime_hub=self.realtime_hub,
            worker_name=settings.durable_job_worker_name,
        )

    def initialize(self) -> None:
        self.bootstrap_schema_and_seed()
