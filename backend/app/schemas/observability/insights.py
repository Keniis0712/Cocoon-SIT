from datetime import datetime

from pydantic import BaseModel


class InsightMetric(BaseModel):
    name: str
    value: int | float


class ModelUsageMetric(BaseModel):
    provider_kind: str
    model_name: str
    call_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class WorkflowMetrics(BaseModel):
    wakeup_runs: int = 0
    pull_total: int = 0
    pull_success_rate: float = 0
    merge_total: int = 0
    merge_success_rate: float = 0
    compaction_runs: int = 0
    artifact_cleanup_runs: int = 0


class FailedRoundMetric(BaseModel):
    event_type: str
    reason: str
    count: int


class RelationScorePoint(BaseModel):
    cocoon_id: str
    action_id: str | None
    relation_score: int
    created_at: datetime


class InsightsSummary(BaseModel):
    metrics: list[InsightMetric]
    action_status_counts: dict[str, int]
    durable_job_status_counts: dict[str, int]
    operation_counts: dict[str, int]
    model_usage: list[ModelUsageMetric]
    workflow_metrics: WorkflowMetrics
    failed_rounds: list[FailedRoundMetric]
    relation_score_timeline: list[RelationScorePoint]
