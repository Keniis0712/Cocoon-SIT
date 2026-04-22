from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator


class MemoryCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    scope: StrictStr = "dialogue"
    summary: StrictStr
    content: StrictStr
    tags: list["TagReferenceModel"] = Field(default_factory=list)
    owner_user_id: StrictStr | None = None
    importance: StrictInt = 5


class TagOperationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["add", "remove"]
    tag: StrictStr


class TagReferenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tag: StrictStr


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
    schedule_wakeups: list[ScheduledWakeupModel | dict[str, Any]] = Field(default_factory=list)
    cancel_wakeup_task_ids: list[StrictStr] = Field(default_factory=list)
    generation_brief: StrictStr | None = None
    memory_candidates: list[MemoryCandidateModel] = Field(default_factory=list)


class GenerationStructuredOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reply_text: StrictStr
