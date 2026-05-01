from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class MemoryChunkOut(ORMModel):
    id: str
    cocoon_id: str | None = None
    chat_group_id: str | None = None
    owner_user_id: str | None = None
    memory_pool: str
    memory_type: str
    scope: str
    summary: str | None
    content: str
    tags_json: list[str]
    tag_labels: list[str] = Field(default_factory=list)
    importance: int
    confidence: int
    status: str
    valid_until: datetime | None = None
    last_accessed_at: datetime | None = None
    access_count: int
    source_kind: str
    meta_json: dict = Field(default_factory=dict)
    created_at: datetime


class MemoryOverviewOut(BaseModel):
    total: int
    by_pool: dict[str, int]
    by_type: dict[str, int]
    by_status: dict[str, int]
    tag_cloud: list[dict]
    word_cloud: list[dict]
    importance_average: float
    confidence_average: float


class MemoryListOut(BaseModel):
    items: list[MemoryChunkOut]
    overview: MemoryOverviewOut


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    summary: str | None = None
    tags_json: list[str] | None = None
    importance: int | None = Field(default=None, ge=0, le=5)
    confidence: int | None = Field(default=None, ge=1, le=5)
    status: str | None = None


class MemoryReorganizeRequest(BaseModel):
    memory_ids: list[str] = Field(default_factory=list)
    instructions: str | None = None


class MemoryCompactionRequest(BaseModel):
    before_message_id: str | None = None
