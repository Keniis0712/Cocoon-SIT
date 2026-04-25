from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


InsightsRange = Literal["24h", "7d", "30d", "90d"]
InsightsInterval = Literal["auto", "hour", "day"]
ResolvedInsightsInterval = Literal["hour", "day"]


class NamedMetric(BaseModel):
    name: str
    value: int | float


class TimeSeriesPoint(BaseModel):
    bucket: str
    value: int | float


class RankedCocoonMetric(BaseModel):
    cocoon_id: str
    cocoon_name: str
    value: int | float


class InsightsSummary(BaseModel):
    total_messages: int = 0
    total_runs: int = 0
    total_tokens: int = 0
    error_rate: float = 0
    average_latency_ms: float = 0
    active_cocoons: int = 0
    pending_wakeup_count: int = 0


class TokenUsageInsights(BaseModel):
    series: list[TimeSeriesPoint]
    by_provider: list[NamedMetric]
    by_model: list[NamedMetric]
    by_operation: list[NamedMetric]


class MemoryInsights(BaseModel):
    total_memories: int = 0
    growth: list[TimeSeriesPoint]
    by_source_kind: list[NamedMetric]
    by_memory_type: list[NamedMetric]
    top_cocoons: list[RankedCocoonMetric]


class RuntimeInsights(BaseModel):
    request_series: list[TimeSeriesPoint]
    decision_distribution: list[NamedMetric]
    status_distribution: list[NamedMetric]
    node_latency: list[NamedMetric]
    latency_p50_ms: float = 0
    latency_p95_ms: float = 0
    silence_rate: float = 0
    wakeup_rate: float = 0
    error_rate: float = 0
    top_error_cocoons: list[RankedCocoonMetric]


class InsightsDashboard(BaseModel):
    generated_at: datetime
    range: InsightsRange
    interval: ResolvedInsightsInterval
    summary: InsightsSummary
    token_usage: TokenUsageInsights
    memory: MemoryInsights
    runtime: RuntimeInsights
