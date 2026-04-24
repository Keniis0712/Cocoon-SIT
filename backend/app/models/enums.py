from __future__ import annotations

from enum import StrEnum


class ActionStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class DurableJobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class DurableJobType(StrEnum):
    pull = "pull"
    merge = "merge"
    wakeup = "wakeup"
    plugin_im_delivery = "plugin_im_delivery"
    rollback = "rollback"
    compaction = "compaction"
    artifact_cleanup = "artifact_cleanup"


class PromptTemplateType(StrEnum):
    system = "system"
    meta = "meta"
    generator = "generator"
    memory_summary = "memory_summary"
    pull = "pull"
    merge = "merge"
    audit_summary = "audit_summary"


class ArtifactKind(StrEnum):
    prompt_snapshot = "prompt_snapshot"
    prompt_variables = "prompt_variables"
    memory_retrieval = "memory_retrieval"
    meta_output = "meta_output"
    provider_raw_output = "provider_raw_output"
    generator_output = "generator_output"
    side_effects_result = "side_effects_result"
    compaction_result = "compaction_result"
    merge_conflict_report = "merge_conflict_report"
    workflow_summary = "workflow_summary"
    audit_summary = "audit_summary"
