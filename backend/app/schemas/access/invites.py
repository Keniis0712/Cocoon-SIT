from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class InviteCreate(BaseModel):
    code: str = Field(min_length=4)
    quota_total: int = Field(default=1, ge=1)
    expires_at: datetime | None = None
    created_for_user_id: str | None = None
    source_type: str = Field(default="ADMIN_OVERRIDE", min_length=1)
    source_id: str | None = None


class InviteRevokeResult(ORMModel):
    code: str
    revoked_at: datetime


class InviteRedeemRequest(BaseModel):
    user_id: str
    quota: int = Field(default=1, ge=1)


class InviteGrantCreate(BaseModel):
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    amount: int = Field(default=1, ge=1)
    is_unlimited: bool = False
    note: str | None = None


class InviteOut(ORMModel):
    id: str
    code: str
    created_by_user_id: str | None
    created_for_user_id: str | None
    source_type: str
    source_id: str | None
    quota_total: int
    quota_used: int
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InviteGrantOut(ORMModel):
    id: str
    invite_code_id: str | None
    granted_by_user_id: str | None
    source_type: str
    source_id: str | None
    target_type: str
    target_id: str
    quota: int
    is_unlimited: bool
    note: str | None
    created_at: datetime


class InviteSummaryOut(ORMModel):
    target_type: str
    target_id: str
    invite_quota_remaining: int
    invite_quota_unlimited: bool


class InviteRedeemResult(ORMModel):
    invite_code_id: str
    grant_id: str
    quota_used: int
