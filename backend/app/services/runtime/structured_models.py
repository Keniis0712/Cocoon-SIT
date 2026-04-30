from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator


class TagOperationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["add", "remove"]
    tag_index: StrictInt


class ScheduledWakeupModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reason: StrictStr
    run_at: StrictStr | None = None
    delay_seconds: StrictInt | None = None
    delay_minutes: StrictInt | None = None
    delay_hours: StrictInt | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason is required")
        return normalized


class MemoryTagReferenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tag: StrictStr


class FactCacheOperationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    op: Literal["upsert", "delete"] = "upsert"
    cache_key: StrictStr
    content: StrictStr = ""
    summary: StrictStr | None = None
    valid_until: StrictStr | None = None
    meta_json: dict[str, Any] = Field(default_factory=dict)


class MemoryOperationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    op: Literal["none", "candidate", "upsert", "update", "archive"] = "none"
    content: StrictStr = ""
    summary: StrictStr | None = None
    memory_type: StrictStr = "preference"
    memory_pool: StrictStr | None = None
    tags: list[MemoryTagReferenceModel | StrictStr] = Field(default_factory=list)
    importance: StrictInt = 3
    confidence: StrictInt = 3
    reason: StrictStr | None = None
    valid_until: StrictStr | None = None
    target_memory_id: StrictStr | None = None
    supersedes_memory_ids: list[StrictStr] = Field(default_factory=list)


class SessionUpdateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    persona_patch: dict[str, Any] = Field(default_factory=dict)
    relation_delta: StrictInt = 0
    tag_ops: list[TagOperationModel] = Field(default_factory=list)


class TaskStateUpdateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_name: StrictStr | None = None
    goal: StrictStr | None = None
    progress: StrictStr | None = None
    status: StrictStr | None = None
    expires_at: StrictStr | None = None
    completed: bool = False
    meta_json: dict[str, Any] = Field(default_factory=dict)


class MetaStructuredOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision: Literal["reply", "silence"] = "reply"
    relation_delta: StrictInt = 0
    persona_patch: dict[str, Any] = Field(default_factory=dict)
    tag_ops: list[TagOperationModel] = Field(default_factory=list)
    internal_thought: StrictStr = ""
    event_summary: StrictStr | None = None
    schedule_wakeups: list[ScheduledWakeupModel | dict[str, Any]] = Field(default_factory=list)
    cancel_wakeup_task_ids: list[StrictStr] = Field(default_factory=list)
    generation_brief: StrictStr | None = None
    used_memory_ids: list[StrictStr] = Field(default_factory=list)
    session_update: SessionUpdateModel = Field(default_factory=SessionUpdateModel)
    task_state_update: TaskStateUpdateModel = Field(default_factory=TaskStateUpdateModel)
    fact_cache_ops: list[FactCacheOperationModel] = Field(default_factory=list)
    memory_ops: list[MemoryOperationModel] = Field(default_factory=list)


class GenerationStructuredOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reply_text: StrictStr


class CompactionMemoryItemModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    scope: StrictStr = "summary"
    summary: StrictStr
    content: StrictStr
    tag_indexes: list[StrictInt] = Field(default_factory=list)
    importance: StrictInt = 5
    confidence: StrictInt = 4
    memory_type: StrictStr = "summary"
    memory_pool: StrictStr | None = None


class CompactionStructuredOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    summary: StrictStr = ""
    long_term_memories: list[CompactionMemoryItemModel] = Field(default_factory=list)


class ReplyOnlyStructuredOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reply_text: StrictStr
    internal_thought: StrictStr = ""


class SinglePassStructuredOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reply_text: StrictStr
    internal_thought: StrictStr = ""
    decision: Literal["reply", "silence"] = "reply"
    generation_brief: StrictStr | None = None
    event_summary: StrictStr | None = None
    used_memory_ids: list[StrictStr] = Field(default_factory=list)
    session_update: SessionUpdateModel = Field(default_factory=SessionUpdateModel)
    task_state_update: TaskStateUpdateModel = Field(default_factory=TaskStateUpdateModel)
    fact_cache_ops: list[FactCacheOperationModel] = Field(default_factory=list)
    memory_ops: list[MemoryOperationModel] = Field(default_factory=list)
    schedule_wakeups: list[ScheduledWakeupModel | dict[str, Any]] = Field(default_factory=list)
    cancel_wakeup_task_ids: list[StrictStr] = Field(default_factory=list)
