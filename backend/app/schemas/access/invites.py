from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class InviteCreate(BaseModel):
    code: str = Field(min_length=4)
    quota_total: int = Field(default=1, ge=1)
    expires_at: datetime | None = None


class InviteRedeemRequest(BaseModel):
    user_id: str
    quota: int = Field(default=1, ge=1)


class InviteOut(ORMModel):
    id: str
    code: str
    created_by_user_id: str | None
    quota_total: int
    quota_used: int
    expires_at: datetime | None
    created_at: datetime


class InviteRedeemResult(ORMModel):
    invite_code_id: str
    grant_id: str
    quota_used: int
