from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TagCreate(BaseModel):
    tag_id: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    visibility: str = "private"
    is_isolated: bool = False
    meta_json: dict = Field(default_factory=dict)
    visible_chat_group_ids: list[str] = Field(default_factory=list)


class TagUpdate(BaseModel):
    brief: str | None = None
    visibility: str | None = None
    is_isolated: bool | None = None
    meta_json: dict | None = None
    visible_chat_group_ids: list[str] | None = None


class TagOut(ORMModel):
    id: str
    tag_id: str
    brief: str
    visibility: str
    is_isolated: bool
    is_system: bool
    meta_json: dict
    visible_chat_group_ids: list[str]
    created_at: datetime


class TagChatGroupVisibilityUpdate(BaseModel):
    chat_group_ids: list[str] = Field(default_factory=list)


class TagChatGroupVisibilityOut(ORMModel):
    tag_id: str
    chat_group_ids: list[str]
