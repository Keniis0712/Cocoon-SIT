from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import DurableJob
from app.models.entities import DurableJobType
from app.services.audit.service import AuditService
from app.services.jobs.durable_jobs import DurableJobService
from app.services.prompts.service import PromptTemplateService
from app.services.providers.registry import ProviderRegistry
from app.services.runtime.orchestration.chat_runtime import ChatRuntime
from app.services.runtime.orchestration.round_cleanup import RoundCleanupService
from app.worker.jobs.artifact_cleanup_job_service import ArtifactCleanupJobService
from app.worker.jobs.compaction_job_service import CompactionJobService
from app.worker.jobs.memory_maintenance_job_service import MemoryMaintenanceJobService
from app.worker.jobs.memory_reorganize_job_service import MemoryReorganizeJobService
from app.worker.jobs.rollback_job_service import RollbackJobService
from app.worker.jobs.runtime_action_service import RuntimeActionService
from app.worker.jobs.runtime_job_service import RuntimeJobService


class DurableJobExecutor:
    def __init__(
        self,
        chat_runtime: ChatRuntime,
        durable_jobs: DurableJobService,
        audit_service: AuditService,
        round_cleanup: RoundCleanupService,
        prompt_service: PromptTemplateService,
        provider_registry: ProviderRegistry,
    ) -> None:
        self.chat_runtime = chat_runtime
        self.durable_jobs = durable_jobs
        self.audit_service = audit_service
        self.round_cleanup = round_cleanup
        self.prompt_service = prompt_service
        self.provider_registry = provider_registry
        self.runtime_action_service = RuntimeActionService()
        self.rollback_job_service = RollbackJobService(audit_service, round_cleanup)
        self.compaction_job_service = CompactionJobService(
            audit_service,
            prompt_service,
            provider_registry,
            chat_runtime.context_builder.memory_service,
        )
        self.memory_reorganize_job_service = MemoryReorganizeJobService(
            audit_service,
            prompt_service,
            provider_registry,
            chat_runtime.context_builder.memory_service,
        )
        self.memory_maintenance_job_service = MemoryMaintenanceJobService()
        self.artifact_cleanup_job_service = ArtifactCleanupJobService(audit_service)
        self.runtime_job_service = RuntimeJobService(chat_runtime, self.runtime_action_service)

    def execute(self, session: Session, job: DurableJob) -> None:
        if job.job_type == DurableJobType.rollback:
            self.rollback_job_service.execute(session, job.payload_json["checkpoint_id"])
            return
        if job.job_type == DurableJobType.compaction:
            self.compaction_job_service.execute(
                session,
                job.cocoon_id,
                before_message_id=job.payload_json.get("before_message_id"),
            )
            return
        if job.job_type == DurableJobType.memory_reorganize:
            self.memory_reorganize_job_service.execute(
                session,
                job.cocoon_id,
                memory_ids=job.payload_json.get("memory_ids") or [],
                instructions=job.payload_json.get("instructions"),
            )
            return
        if job.job_type == DurableJobType.memory_maintenance:
            self.memory_maintenance_job_service.execute(session)
            return
        if job.job_type == DurableJobType.artifact_cleanup:
            self.artifact_cleanup_job_service.execute(
                session,
                job.payload_json.get("artifact_ids"),
                mode=job.payload_json.get("mode"),
            )
            return
        if job.job_type == DurableJobType.wakeup:
            self.runtime_job_service.execute_wakeup(session, job)
            return
        if job.job_type == DurableJobType.pull:
            self.runtime_job_service.execute_pull(session, job)
            return
        if job.job_type == DurableJobType.merge:
            self.runtime_job_service.execute_merge(session, job)
            return
        raise ValueError(f"Unsupported durable job type: {job.job_type}")
