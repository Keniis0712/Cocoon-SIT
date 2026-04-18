from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ModelProviderCreate(BaseModel):
    name: str
    kind: str = "openai_compatible"
    base_url: str | None = None
    capabilities_json: dict = Field(default_factory=dict)


class ProviderCredentialCreate(BaseModel):
    secret: str
    metadata_json: dict = Field(default_factory=dict)


class ModelProviderOut(ORMModel):
    id: str
    name: str
    kind: str
    base_url: str | None
    is_enabled: bool
    capabilities_json: dict
    created_at: datetime


class ProviderCredentialOut(ORMModel):
    id: str
    provider_id: str
    metadata_json: dict
    created_at: datetime
    updated_at: datetime
    masked_secret: str = ""
