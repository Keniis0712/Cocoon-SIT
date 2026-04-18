from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class CheckpointOut(ORMModel):
    id: str
    cocoon_id: str
    anchor_message_id: str
    label: str
    is_active: bool
    created_at: datetime


class RollbackJobOut(BaseModel):
    durable_job_id: str
    checkpoint_id: str
    status: str
