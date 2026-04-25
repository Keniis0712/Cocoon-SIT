from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import ActionDispatch, Character, ChatGroupRoom, Cocoon, MemoryChunk, Message, SessionState
from app.services.memory.service import MemoryRetrievalHit


@dataclass
class RuntimeEvent:
    event_type: str
    cocoon_id: str | None
    chat_group_id: str | None
    action_id: str
    payload: dict[str, Any]

    @property
    def target_type(self) -> str:
        return "chat_group" if self.chat_group_id else "cocoon"

    @property
    def target_id(self) -> str:
        return self.chat_group_id or self.cocoon_id or ""

    @property
    def channel_key(self) -> str:
        return f"{self.target_type}:{self.target_id}"


@dataclass
class ContextPackage:
    runtime_event: RuntimeEvent
    conversation: Cocoon | ChatGroupRoom
    character: Character
    session_state: SessionState
    visible_messages: list[Message]
    memory_context: list[MemoryChunk]
    memory_owner_user_id: str | None = None
    memory_hits: list[MemoryRetrievalHit] = field(default_factory=list)
    external_context: dict[str, Any] = field(default_factory=dict)

    @property
    def cocoon(self) -> Cocoon | ChatGroupRoom:
        return self.conversation

    @property
    def target_type(self) -> str:
        return self.runtime_event.target_type

    @property
    def target_id(self) -> str:
        return self.runtime_event.target_id

    @property
    def channel_key(self) -> str:
        return self.runtime_event.channel_key


@dataclass
class MetaDecision:
    decision: str
    relation_delta: int
    persona_patch: dict[str, Any]
    tag_ops: list["TagOperation"]
    internal_thought: str
    next_wakeup_hints: list[dict[str, Any]] = field(default_factory=list)
    cancel_wakeup_task_ids: list[str] = field(default_factory=list)
    generation_brief: str | None = None


@dataclass
class MemoryCandidate:
    scope: str
    summary: str
    content: str
    tags: list["TagReference"] = field(default_factory=list)
    owner_user_id: str | None = None
    importance: int = 5


@dataclass
class TagOperation:
    action: str
    tag_index: int


@dataclass
class TagReference:
    tag: str


@dataclass
class GenerationOutput:
    rendered_prompt: str
    chunks: list[str]
    reply_text: str
    raw_response: dict[str, Any]
    structured_output: dict[str, Any]
    usage: dict[str, int]
    provider_kind: str
    model_name: str


@dataclass
class RuntimeResult:
    action: ActionDispatch
    final_message: Message | None
