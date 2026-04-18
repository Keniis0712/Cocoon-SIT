from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import ActionDispatch, Character, Cocoon, MemoryChunk, Message, SessionState
from app.services.memory.service import MemoryRetrievalHit


@dataclass
class RuntimeEvent:
    event_type: str
    cocoon_id: str
    action_id: str
    payload: dict[str, Any]


@dataclass
class ContextPackage:
    runtime_event: RuntimeEvent
    cocoon: Cocoon
    character: Character
    session_state: SessionState
    visible_messages: list[Message]
    memory_context: list[MemoryChunk]
    memory_hits: list[MemoryRetrievalHit] = field(default_factory=list)
    external_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetaDecision:
    decision: str
    relation_delta: int
    persona_patch: dict[str, Any]
    tag_ops: list[str]
    internal_thought: str
    next_wakeup_hint: dict[str, Any] | None


@dataclass
class GenerationOutput:
    rendered_prompt: str
    chunks: list[str]
    full_text: str
    raw_response: dict[str, Any]
    usage: dict[str, int]
    provider_kind: str
    model_name: str


@dataclass
class RuntimeResult:
    action: ActionDispatch
    final_message: Message | None
