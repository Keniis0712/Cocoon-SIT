from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ActionDispatch, AuditArtifact, AuditRun, DurableJob, FailedRound, MemoryChunk, Message, User
from app.schemas.observability.insights import (
    FailedRoundMetric,
    InsightMetric,
    InsightsSummary,
    ModelUsageMetric,
    RelationScorePoint,
    WorkflowMetrics,
)
from app.services.security.authorization_service import AuthorizationService


class InsightQueryService:
    """Builds typed insight summary responses from aggregate queries."""

    def __init__(self, authorization_service: AuthorizationService):
        self.authorization_service = authorization_service

    def summary(self, session: Session, user: User | None = None) -> InsightsSummary:
        runs = list(session.scalars(select(AuditRun)).all())
        if user is not None:
            runs = self.authorization_service.filter_visible_audit_runs(session, user, runs)
        visible_run_ids = {run.id for run in runs}
        visible_cocoon_ids = {run.cocoon_id for run in runs if run.cocoon_id}

        actions = list(session.scalars(select(ActionDispatch)).all())
        if user is not None and not self.authorization_service.is_admin(session, user):
            actions = [item for item in actions if item.cocoon_id in visible_cocoon_ids]
        action_counts: dict[str, int] = defaultdict(int)
        for action in actions:
            action_counts[action.status] += 1

        durable_jobs = list(session.scalars(select(DurableJob)).all())
        if user is not None and not self.authorization_service.is_admin(session, user):
            durable_jobs = [
                item
                for item in durable_jobs
                if item.cocoon_id is not None and item.cocoon_id in visible_cocoon_ids
            ]
        durable_counts: dict[str, int] = defaultdict(int)
        for job in durable_jobs:
            durable_counts[job.status] += 1

        operation_counts: dict[str, int] = defaultdict(int)
        for run in runs:
            operation_counts[run.operation_type] += 1

        metrics = [
            InsightMetric(name="users", value=session.execute(select(func.count()).select_from(User)).scalar_one()),
            InsightMetric(
                name="messages",
                value=(
                    session.execute(select(func.count()).select_from(Message)).scalar_one()
                    if user is None or self.authorization_service.is_admin(session, user)
                    else len(
                        list(
                            session.scalars(
                                select(Message).where(Message.cocoon_id.in_(visible_cocoon_ids))
                            ).all()
                        )
                    )
                ),
            ),
            InsightMetric(
                name="memory_chunks",
                value=(
                    session.execute(select(func.count()).select_from(MemoryChunk)).scalar_one()
                    if user is None or self.authorization_service.is_admin(session, user)
                    else len(
                        list(
                            session.scalars(
                                select(MemoryChunk).where(MemoryChunk.cocoon_id.in_(visible_cocoon_ids))
                            ).all()
                        )
                    )
                ),
            ),
            InsightMetric(
                name="audit_runs",
                value=len(runs),
            ),
        ]
        artifacts = (
            list(
                session.scalars(
                    select(AuditArtifact).where(AuditArtifact.run_id.in_(visible_run_ids))
                ).all()
            )
            if visible_run_ids
            else []
        )
        usage_by_model: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: {
                "call_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        )
        relation_timeline: list[RelationScorePoint] = []
        for artifact in artifacts:
            if artifact.kind == "provider_raw_output":
                provider_kind = str(artifact.metadata_json.get("provider_kind") or "unknown")
                model_name = str(artifact.metadata_json.get("model_name") or "unknown")
                bucket = usage_by_model[(provider_kind, model_name)]
                bucket["call_count"] += 1
                bucket["prompt_tokens"] += int(artifact.metadata_json.get("prompt_tokens") or 0)
                bucket["completion_tokens"] += int(artifact.metadata_json.get("completion_tokens") or 0)
                bucket["total_tokens"] += int(artifact.metadata_json.get("total_tokens") or 0)
            if artifact.kind == "side_effects_result":
                run = next((item for item in runs if item.id == artifact.run_id), None)
                if run and run.cocoon_id is not None:
                    relation_timeline.append(
                        RelationScorePoint(
                            cocoon_id=run.cocoon_id,
                            action_id=artifact.metadata_json.get("action_id"),
                            relation_score=int(artifact.metadata_json.get("relation_score") or 0),
                            created_at=artifact.created_at,
                        )
                    )

        failed_rounds = list(session.scalars(select(FailedRound)).all())
        if user is not None and not self.authorization_service.is_admin(session, user):
            failed_rounds = [item for item in failed_rounds if item.cocoon_id in visible_cocoon_ids]
        failed_round_buckets: dict[tuple[str, str], int] = defaultdict(int)
        for item in failed_rounds:
            failed_round_buckets[(item.event_type, item.reason)] += 1

        pull_runs = [run for run in runs if run.operation_type == "pull"]
        merge_runs = [run for run in runs if run.operation_type == "merge"]
        workflow_metrics = WorkflowMetrics(
            wakeup_runs=sum(1 for run in runs if run.operation_type == "wakeup"),
            pull_total=len(pull_runs),
            pull_success_rate=(
                sum(1 for run in pull_runs if run.status == "completed") / len(pull_runs)
                if pull_runs
                else 0
            ),
            merge_total=len(merge_runs),
            merge_success_rate=(
                sum(1 for run in merge_runs if run.status == "completed") / len(merge_runs)
                if merge_runs
                else 0
            ),
            compaction_runs=sum(1 for run in runs if run.operation_type == "compaction"),
            artifact_cleanup_runs=sum(1 for job in durable_jobs if job.job_type == "artifact_cleanup"),
        )
        return InsightsSummary(
            metrics=metrics,
            action_status_counts=dict(action_counts),
            durable_job_status_counts=dict(durable_counts),
            operation_counts=dict(operation_counts),
            model_usage=[
                ModelUsageMetric(
                    provider_kind=provider_kind,
                    model_name=model_name,
                    call_count=bucket["call_count"],
                    prompt_tokens=bucket["prompt_tokens"],
                    completion_tokens=bucket["completion_tokens"],
                    total_tokens=bucket["total_tokens"],
                )
                for (provider_kind, model_name), bucket in sorted(usage_by_model.items())
            ],
            workflow_metrics=workflow_metrics,
            failed_rounds=[
                FailedRoundMetric(event_type=event_type, reason=reason, count=count)
                for (event_type, reason), count in sorted(failed_round_buckets.items())
            ],
            relation_score_timeline=sorted(
                relation_timeline,
                key=lambda item: item.created_at,
            )[-20:],
        )
