from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1)
    prompt_summary: str = ""
    settings_json: dict = Field(default_factory=dict)


class CharacterUpdate(BaseModel):
    name: str | None = None
    prompt_summary: str | None = None
    settings_json: dict | None = None


class CharacterAclCreate(BaseModel):
    subject_type: str
    subject_id: str
    can_read: bool = True
    can_use: bool = True


class CharacterOut(ORMModel):
    id: str
    name: str
    prompt_summary: str
    settings_json: dict
    created_by_user_id: str | None
    created_at: datetime


class CharacterAclOut(ORMModel):
    id: str
    character_id: str
    subject_type: str
    subject_id: str
    can_read: bool
    can_use: bool
    created_at: datetime
