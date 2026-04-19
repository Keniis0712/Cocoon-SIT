from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.workspace.cocoons import ChatMessageCreate


class ChatGroupRoomCreate(BaseModel):
    name: str = Field(min_length=1)
    character_id: str
    selected_model_id: str
    default_temperature: float | None = None
    max_context_messages: int | None = Field(default=None, ge=1)
    auto_compaction_enabled: bool | None = None
    external_platform: str | None = None
    external_group_id: str | None = None
    external_account_id: str | None = None
    initial_member_ids: list[str] = Field(default_factory=list)


class ChatGroupRoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    character_id: str | None = None
    selected_model_id: str | None = None
    default_temperature: float | None = None
    max_context_messages: int | None = Field(default=None, ge=1)
    auto_compaction_enabled: bool | None = None
    external_platform: str | None = None
    external_group_id: str | None = None
    external_account_id: str | None = None


class ChatGroupRoomOut(ORMModel):
    id: str
    name: str
    owner_user_id: str
    character_id: str
    selected_model_id: str
    default_temperature: float
    max_context_messages: int
    auto_compaction_enabled: bool
    external_platform: str | None
    external_group_id: str | None
    external_account_id: str | None
    created_at: datetime


class ChatGroupMemberCreate(BaseModel):
    user_id: str
    member_role: str = "member"


class ChatGroupMemberUpdate(BaseModel):
    member_role: str


class ChatGroupMemberOut(ORMModel):
    id: str
    room_id: str
    user_id: str
    member_role: str
    created_at: datetime


class ChatGroupStateOut(ORMModel):
    id: str
    cocoon_id: str | None = None
    chat_group_id: str
    relation_score: int
    persona_json: dict
    active_tags_json: list[str]
    current_wakeup_task_id: str | None


class ChatGroupMessageCreate(ChatMessageCreate):
    pass


class MessageRetractResult(ORMModel):
    message_id: str
    is_retracted: bool
    retracted_at: datetime | None
    retracted_by_user_id: str | None
    retraction_note: str | None
