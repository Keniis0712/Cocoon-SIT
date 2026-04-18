from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AcceptedResponse(BaseModel):
    accepted: bool = True
    action_id: str
    status: str
    debounce_until: int | None = None


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    now: datetime
