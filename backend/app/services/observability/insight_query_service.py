from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditArtifact,
    AuditRun,
    AuditStep,
    ChatGroupRoom,
    Cocoon,
    FailedRound,
    MemoryChunk,
    Message,
    User,
    WakeupTask,
)
from app.schemas.observability.insights import (
    InsightsDashboard,
    InsightsInterval,
    InsightsRange,
    MemoryInsights,
    NamedMetric,
    RankedCocoonMetric,
    ResolvedInsightsInterval,
    RuntimeInsights,
    TimeSeriesPoint,
    TokenUsageInsights,
    InsightsSummary,
)
from app.services.security.authorization_service import AuthorizationService
from app.services.storage.base import ArtifactStore


@dataclass(frozen=True)
class DashboardWindow:
    range: InsightsRange
    interval: ResolvedInsightsInterval
    start: datetime
    end: datetime


class InsightQueryService:
    """Builds typed dashboard responses from observability records."""

    def __init__(self, authorization_service: AuthorizationService, artifact_store: ArtifactStore):
        self.authorization_service = authorization_service
        self.artifact_store = artifact_store

    def dashboard(
        self,
        session: Session,
        user: User | None = None,
        *,
        range: InsightsRange = "30d",
        interval: InsightsInterval = "auto",
    ) -> InsightsDashboard:
        window = self._resolve_window(range=range, interval=interval)
        visible = self._resolve_visibility(session, user)

        runs = [
            run
            for run in session.scalars(select(AuditRun).order_by(AuditRun.started_at.asc())).all()
            if self._is_visible_run(run, visible)
        ]
        runs_in_range = [run for run in runs if self._in_window(run.started_at, window)]
        visible_run_ids = {run.id for run in runs}
        run_by_id = {run.id: run for run in runs}
        cocoon_names = {item.id: item.name for item in visible["cocoons"]}

        artifacts = [
            artifact
            for artifact in session.scalars(select(AuditArtifact).order_by(AuditArtifact.created_at.asc())).all()
            if artifact.run_id in visible_run_ids and self._in_window(artifact.created_at, window)
        ]
        provider_artifacts = [artifact for artifact in artifacts if artifact.kind == "provider_raw_output"]
        meta_artifacts = [artifact for artifact in artifacts if artifact.kind == "meta_output"]

        messages = [
            message
            for message in session.scalars(select(Message).order_by(Message.created_at.asc())).all()
            if self._is_visible_message(message, visible) and self._in_window(message.created_at, window)
        ]
        memories = [
            memory
            for memory in session.scalars(select(MemoryChunk).order_by(MemoryChunk.created_at.asc())).all()
            if self._is_visible_memory(memory, visible, user) and self._in_window(memory.created_at, window)
        ]
        steps = [
            step
            for step in session.scalars(select(AuditStep)).all()
            if step.run_id in visible_run_ids and self._in_window(step.started_at, window)
        ]
        failed_rounds = [
            item
            for item in session.scalars(select(FailedRound).order_by(FailedRound.created_at.asc())).all()
            if self._is_visible_failed_round(item, visible) and self._in_window(item.created_at, window)
        ]
        pending_wakeups = [
            item
            for item in session.scalars(select(WakeupTask)).all()
            if item.status == "queued" and self._is_visible_wakeup(item, visible)
        ]

        run_latencies = self._latencies_ms(runs_in_range)
        token_total = sum(int(artifact.metadata_json.get("total_tokens") or 0) for artifact in provider_artifacts)
        failed_run_count = sum(1 for run in runs_in_range if str(run.status) != "completed")
        wakeup_run_count = sum(1 for run in runs_in_range if run.operation_type == "wakeup")

        summary = InsightsSummary(
            total_messages=len(messages),
            total_runs=len(runs_in_range),
            total_tokens=token_total,
            error_rate=(failed_run_count / len(runs_in_range)) if runs_in_range else 0,
            average_latency_ms=round(mean(run_latencies), 2) if run_latencies else 0,
            active_cocoons=len({run.cocoon_id for run in runs_in_range if run.cocoon_id}),
            pending_wakeup_count=len(pending_wakeups),
        )

        token_usage = TokenUsageInsights(
            series=self._bucket_series(
                window,
                (
                    (artifact.created_at, int(artifact.metadata_json.get("total_tokens") or 0))
                    for artifact in provider_artifacts
                ),
            ),
            by_provider=self._counter_metrics(
                Counter(str(artifact.metadata_json.get("provider_kind") or "unknown") for artifact in provider_artifacts),
                value_getter=lambda key: sum(
                    int(item.metadata_json.get("total_tokens") or 0)
                    for item in provider_artifacts
                    if str(item.metadata_json.get("provider_kind") or "unknown") == key
                ),
            ),
            by_model=self._counter_metrics(
                Counter(str(artifact.metadata_json.get("model_name") or "unknown") for artifact in provider_artifacts),
                value_getter=lambda key: sum(
                    int(item.metadata_json.get("total_tokens") or 0)
                    for item in provider_artifacts
                    if str(item.metadata_json.get("model_name") or "unknown") == key
                ),
            ),
            by_operation=self._counter_metrics(
                Counter(run_by_id[item.run_id].operation_type for item in provider_artifacts if item.run_id in run_by_id),
                value_getter=lambda key: sum(
                    int(item.metadata_json.get("total_tokens") or 0)
                    for item in provider_artifacts
                    if item.run_id in run_by_id and run_by_id[item.run_id].operation_type == key
                ),
            ),
        )

        memory_counts_by_cocoon = Counter(memory.cocoon_id for memory in memories if memory.cocoon_id)
        memory = MemoryInsights(
            total_memories=len(memories),
            growth=self._bucket_series(window, ((memory.created_at, 1) for memory in memories)),
            by_source_kind=self._counter_metrics(
                Counter(str((memory.meta_json or {}).get("source_kind") or "unknown") for memory in memories)
            ),
            by_memory_type=self._counter_metrics(Counter(str(memory.scope or "unknown") for memory in memories)),
            top_cocoons=self._ranked_cocoons(memory_counts_by_cocoon, cocoon_names),
        )

        decisions = Counter()
        for artifact in meta_artifacts:
            decision = str(artifact.metadata_json.get("decision") or "").strip()
            if not decision:
                payload = self._load_artifact_payload(artifact)
                if isinstance(payload, dict):
                    decision = str(payload.get("decision") or "").strip()
            if decision:
                decisions[decision] += 1

        failed_cocoon_counts = Counter(item.cocoon_id for item in failed_rounds if item.cocoon_id)
        if not failed_cocoon_counts:
            failed_cocoon_counts = Counter(
                run.cocoon_id for run in runs_in_range if run.cocoon_id and str(run.status) != "completed"
            )

        runtime = RuntimeInsights(
            request_series=self._bucket_series(window, ((run.started_at, 1) for run in runs_in_range)),
            decision_distribution=self._counter_metrics(decisions),
            status_distribution=self._counter_metrics(Counter(str(run.status) for run in runs_in_range)),
            node_latency=self._node_latency_metrics(steps),
            latency_p50_ms=self._percentile(run_latencies, 0.5),
            latency_p95_ms=self._percentile(run_latencies, 0.95),
            silence_rate=(decisions.get("silence", 0) / sum(decisions.values())) if decisions else 0,
            wakeup_rate=(wakeup_run_count / len(runs_in_range)) if runs_in_range else 0,
            error_rate=summary.error_rate,
            top_error_cocoons=self._ranked_cocoons(failed_cocoon_counts, cocoon_names),
        )

        return InsightsDashboard(
            generated_at=datetime.now(UTC).replace(tzinfo=None),
            range=window.range,
            interval=window.interval,
            summary=summary,
            token_usage=token_usage,
            memory=memory,
            runtime=runtime,
        )

    def _resolve_window(self, *, range: InsightsRange, interval: InsightsInterval) -> DashboardWindow:
        now = datetime.now(UTC).replace(tzinfo=None)
        delta = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90),
        }[range]
        resolved_interval: ResolvedInsightsInterval = (
            "hour" if range == "24h" else "day"
        ) if interval == "auto" else interval
        return DashboardWindow(
            range=range,
            interval=resolved_interval,
            start=now - delta,
            end=now,
        )

    def _resolve_visibility(self, session: Session, user: User | None) -> dict[str, object]:
        cocoons = list(session.scalars(select(Cocoon).order_by(Cocoon.created_at.asc())).all())
        chat_groups = list(session.scalars(select(ChatGroupRoom).order_by(ChatGroupRoom.created_at.asc())).all())
        if user is not None and not self.authorization_service.is_admin(session, user):
            cocoons = self.authorization_service.filter_visible_cocoons(session, user, cocoons, write=False)
            chat_groups = self.authorization_service.filter_visible_chat_groups(session, user, chat_groups)
        return {
            "is_admin": bool(user and self.authorization_service.is_admin(session, user)),
            "cocoons": cocoons,
            "chat_groups": chat_groups,
            "cocoon_ids": {item.id for item in cocoons},
            "chat_group_ids": {item.id for item in chat_groups},
        }

    def _is_visible_run(self, run: AuditRun, visible: dict[str, object]) -> bool:
        if run.cocoon_id is not None:
            return run.cocoon_id in visible["cocoon_ids"]
        if run.chat_group_id is not None:
            return run.chat_group_id in visible["chat_group_ids"]
        return bool(visible["is_admin"])

    def _is_visible_message(self, message: Message, visible: dict[str, object]) -> bool:
        if message.cocoon_id is not None:
            return message.cocoon_id in visible["cocoon_ids"]
        if message.chat_group_id is not None:
            return message.chat_group_id in visible["chat_group_ids"]
        return False

    def _is_visible_memory(self, memory: MemoryChunk, visible: dict[str, object], user: User | None) -> bool:
        if memory.cocoon_id is not None:
            return memory.cocoon_id in visible["cocoon_ids"]
        if memory.chat_group_id is not None:
            return memory.chat_group_id in visible["chat_group_ids"]
        if memory.owner_user_id is not None and user is not None:
            return bool(visible["is_admin"]) or memory.owner_user_id == user.id
        return bool(visible["is_admin"])

    def _is_visible_failed_round(self, item: FailedRound, visible: dict[str, object]) -> bool:
        if item.cocoon_id is not None:
            return item.cocoon_id in visible["cocoon_ids"]
        if item.chat_group_id is not None:
            return item.chat_group_id in visible["chat_group_ids"]
        return False

    def _is_visible_wakeup(self, item: WakeupTask, visible: dict[str, object]) -> bool:
        if item.cocoon_id is not None:
            return item.cocoon_id in visible["cocoon_ids"]
        if item.chat_group_id is not None:
            return item.chat_group_id in visible["chat_group_ids"]
        return False

    def _in_window(self, value: datetime | None, window: DashboardWindow) -> bool:
        return value is not None and window.start <= value <= window.end

    def _latencies_ms(self, runs: list[AuditRun]) -> list[float]:
        result: list[float] = []
        for run in runs:
            if run.started_at is None or run.finished_at is None:
                continue
            duration = (run.finished_at - run.started_at).total_seconds() * 1000
            if duration >= 0:
                result.append(duration)
        return result

    def _bucket_start(self, value: datetime, interval: ResolvedInsightsInterval) -> datetime:
        if interval == "hour":
            return value.replace(minute=0, second=0, microsecond=0)
        return value.replace(hour=0, minute=0, second=0, microsecond=0)

    def _bucket_label(self, value: datetime, interval: ResolvedInsightsInterval) -> str:
        if interval == "hour":
            return value.strftime("%m-%d %H:00")
        return value.strftime("%Y-%m-%d")

    def _bucket_series(
        self,
        window: DashboardWindow,
        items,
    ) -> list[TimeSeriesPoint]:
        buckets: dict[datetime, float] = {}
        current = self._bucket_start(window.start, window.interval)
        step = timedelta(hours=1) if window.interval == "hour" else timedelta(days=1)
        last_bucket = self._bucket_start(window.end, window.interval)
        while current <= last_bucket:
            buckets[current] = 0
            current += step
        for timestamp, value in items:
            bucket = self._bucket_start(timestamp, window.interval)
            if bucket in buckets:
                buckets[bucket] += float(value)
        return [
            TimeSeriesPoint(bucket=self._bucket_label(bucket, window.interval), value=value)
            for bucket, value in sorted(buckets.items())
        ]

    def _counter_metrics(
        self,
        counter: Counter[str],
        *,
        value_getter=None,
    ) -> list[NamedMetric]:
        metrics: list[NamedMetric] = []
        for name, count in counter.most_common():
            value = value_getter(name) if value_getter is not None else count
            metrics.append(NamedMetric(name=name, value=value))
        return metrics

    def _node_latency_metrics(self, steps: list[AuditStep]) -> list[NamedMetric]:
        buckets: dict[str, list[float]] = defaultdict(list)
        for step in steps:
            if step.started_at is None or step.finished_at is None:
                continue
            duration = (step.finished_at - step.started_at).total_seconds() * 1000
            if duration >= 0:
                buckets[step.step_name].append(duration)
        return [
            NamedMetric(name=name, value=round(mean(values), 2))
            for name, values in sorted(buckets.items(), key=lambda item: mean(item[1]), reverse=True)
        ]

    def _percentile(self, values: list[float], ratio: float) -> float:
        if not values:
            return 0
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * ratio)))
        return round(ordered[index], 2)

    def _ranked_cocoons(
        self,
        counter: Counter[str],
        cocoon_names: dict[str, str],
        *,
        limit: int = 8,
    ) -> list[RankedCocoonMetric]:
        ranked: list[RankedCocoonMetric] = []
        for cocoon_id, value in counter.most_common(limit):
            if not cocoon_id:
                continue
            ranked.append(
                RankedCocoonMetric(
                    cocoon_id=cocoon_id,
                    cocoon_name=cocoon_names.get(cocoon_id, cocoon_id),
                    value=value,
                )
            )
        return ranked

    def _load_artifact_payload(self, artifact: AuditArtifact) -> dict | None:
        if artifact.deleted_at is not None or not artifact.storage_path:
            return None
        try:
            raw = self.artifact_store.read_text(artifact.storage_path)
        except FileNotFoundError:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None
