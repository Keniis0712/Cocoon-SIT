from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TagCreate(BaseModel):
    tag_id: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    is_isolated: bool = False
    meta_json: dict = Field(default_factory=dict)


class TagUpdate(BaseModel):
    brief: str | None = None
    is_isolated: bool | None = None
    meta_json: dict | None = None


class TagOut(ORMModel):
    id: str
    tag_id: str
    brief: str
    is_isolated: bool
    meta_json: dict
    created_at: datetime
