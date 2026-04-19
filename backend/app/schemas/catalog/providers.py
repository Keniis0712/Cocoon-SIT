from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.services.providers.base import ProviderUsage


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


class ProviderTestRequest(BaseModel):
    selected_model_id: str
    prompt: str = Field(min_length=1)


class ProviderUsageOut(ORMModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ProviderTestOut(ORMModel):
    provider_id: str
    selected_model_id: str
    model_name: str
    reply: str
    usage: ProviderUsageOut
    raw_response: dict


class ProviderCredentialOut(ORMModel):
    id: str
    provider_id: str
    metadata_json: dict
    created_at: datetime
    updated_at: datetime
    masked_secret: str = ""
