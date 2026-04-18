from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PromptTemplateUpsertRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    content: str = Field(min_length=1)


class PromptTemplateRevisionOut(ORMModel):
    id: str
    version: int
    content: str
    variables_json: list[str]
    checksum: str
    created_at: datetime


class PromptTemplateOut(ORMModel):
    id: str
    template_type: str
    name: str
    description: str
    active_revision_id: str | None
    created_at: datetime
    updated_at: datetime


class PromptTemplateDetail(PromptTemplateOut):
    active_revision: PromptTemplateRevisionOut | None = None
