from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MemoryCandidateModel(BaseModel):
    scope: str = "dialogue"
    summary: str
    content: str
    tags: list[str] = Field(default_factory=list)
    owner_user_id: str | None = None
    importance: int = 5


class MetaStructuredOutputModel(BaseModel):
    decision: Literal["reply", "silence"] = "reply"
    relation_delta: int = 0
    persona_patch: dict[str, Any] = Field(default_factory=dict)
    tag_ops: list[str] = Field(default_factory=list)
    internal_thought: str = ""
    schedule_wakeups: list[dict[str, Any]] = Field(default_factory=list)
    cancel_wakeup_task_ids: list[str] = Field(default_factory=list)
    generation_brief: str | None = None
    memory_candidates: list[MemoryCandidateModel] = Field(default_factory=list)


class GenerationStructuredOutputModel(BaseModel):
    reply_text: str
