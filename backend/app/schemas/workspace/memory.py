from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class MemoryChunkOut(ORMModel):
    id: str
    scope: str
    summary: str | None
    content: str
    tags_json: list[str]
    created_at: datetime


class MemoryCompactionRequest(BaseModel):
    before_message_id: str | None = None
