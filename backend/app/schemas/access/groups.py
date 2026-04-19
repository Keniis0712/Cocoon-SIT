from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class GroupCreate(BaseModel):
    name: str = Field(min_length=1)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)


class GroupMemberCreate(BaseModel):
    user_id: str
    member_role: str = "member"


class GroupOut(ORMModel):
    id: str
    name: str
    owner_user_id: str | None
    created_at: datetime


class GroupMemberOut(ORMModel):
    id: str
    group_id: str
    user_id: str
    member_role: str
    created_at: datetime
