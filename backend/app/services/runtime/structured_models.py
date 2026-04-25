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


class CompactionStructuredOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    summary: StrictStr = ""
    long_term_memories: list[CompactionMemoryItemModel] = Field(default_factory=list)
