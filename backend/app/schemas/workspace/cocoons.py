from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CocoonCreate(BaseModel):
    name: str
    character_id: str
    selected_model_id: str
    parent_id: str | None = None
    default_temperature: float | None = None
    max_context_messages: int | None = Field(default=None, ge=1)
    auto_compaction_enabled: bool | None = None


class CocoonUpdate(BaseModel):
    name: str | None = None
    character_id: str | None = None
    selected_model_id: str | None = None
    default_temperature: float | None = None
    max_context_messages: int | None = None
    auto_compaction_enabled: bool | None = None


class CocoonOut(ORMModel):
    id: str
    name: str
    owner_user_id: str
    character_id: str
    selected_model_id: str
    default_temperature: float
    max_context_messages: int
    auto_compaction_enabled: bool
    parent_id: str | None
    created_at: datetime


class CocoonTreeNode(BaseModel):
    id: str
    name: str
    parent_id: str | None
    children: list["CocoonTreeNode"] = Field(default_factory=list)


class SessionStateOut(ORMModel):
    id: str
    cocoon_id: str
    chat_group_id: str | None = None
    relation_score: int
    persona_json: dict
    active_tags_json: list[str]
    current_wakeup_task_id: str | None


class CocoonTagBindRequest(BaseModel):
    tag_id: str


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)
    client_request_id: str
    timezone: str | None = None
    client_sent_at: datetime | None = None
    locale: str | None = None
    idle_seconds: int | None = None
    recent_turn_count: int | None = None
    typing_hint_ms: int | None = None


class UserMessageEditRequest(BaseModel):
    message_id: str
    content: str = Field(min_length=1)


class RetryReplyRequest(BaseModel):
    message_id: str | None = None


class RollbackRequest(BaseModel):
    checkpoint_id: str


class ChatMessageOut(ORMModel):
    id: str
    cocoon_id: str | None
    chat_group_id: str | None = None
    action_id: str | None
    client_request_id: str | None
    sender_user_id: str | None = None
    role: str
    content: str
    is_thought: bool
    is_retracted: bool
    retracted_at: datetime | None = None
    retracted_by_user_id: str | None = None
    retraction_note: str | None = None
    tags_json: list[str]
    created_at: datetime


CocoonTreeNode.model_rebuild()
