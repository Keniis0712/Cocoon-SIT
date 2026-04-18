from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AvailableModelCreate(BaseModel):
    provider_id: str
    model_name: str
    model_kind: str = "chat"
    is_default: bool = False
    config_json: dict = Field(default_factory=dict)


class AvailableModelUpdate(BaseModel):
    model_name: str | None = None
    model_kind: str | None = None
    is_default: bool | None = None
    config_json: dict | None = None


class AvailableModelOut(ORMModel):
    id: str
    provider_id: str
    model_name: str
    model_kind: str
    is_default: bool
    config_json: dict
    created_at: datetime
