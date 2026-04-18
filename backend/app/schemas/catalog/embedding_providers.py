from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class EmbeddingProviderCreate(BaseModel):
    name: str
    kind: str = "local_cpu"
    provider_id: str | None = None
    model_name: str
    config_json: dict = Field(default_factory=dict)
    api_key: str | None = None
    is_enabled: bool = True


class EmbeddingProviderUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None
    provider_id: str | None = None
    model_name: str | None = None
    config_json: dict | None = None
    api_key: str | None = None
    is_enabled: bool | None = None


class EmbeddingProviderOut(ORMModel):
    id: str
    name: str
    kind: str
    provider_id: str | None
    model_name: str
    config_json: dict
    is_enabled: bool
    secret_masked: str | None = None
    created_at: datetime
