from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import InviteCode, InviteQuotaGrant, User
from app.schemas.access.invites import (
    InviteCreate,
    InviteGrantCreate,
    InviteGrantOut,
    InviteOut,
    InviteRedeemRequest,
    InviteRedeemResult,
    InviteRevokeResult,
    InviteSummaryOut,
)


router = APIRouter()


@router.get("", response_model=list[InviteOut])
def list_invites(
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:read")),
) -> list[InviteCode]:
    return db.info["container"].invite_service.list_invites(db)


@router.post("", response_model=InviteOut)
def create_invite(
    payload: InviteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("users:write")),
) -> InviteCode:
    return db.info["container"].invite_service.create_invite(db, payload, user)


@router.delete("/{code}", response_model=InviteRevokeResult)
def revoke_invite(
    code: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> InviteRevokeResult:
    invite = db.info["container"].invite_service.revoke_invite(db, code)
    return InviteRevokeResult(code=invite.code, revoked_at=invite.revoked_at)


@router.get("/grants", response_model=list[InviteGrantOut])
def list_invite_grants(
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:read")),
) -> list[InviteQuotaGrant]:
    return db.info["container"].invite_service.list_grants(db)


@router.post("/grants", response_model=InviteGrantOut)
def create_invite_grant(
    payload: InviteGrantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("users:write")),
) -> InviteQuotaGrant:
    return db.info["container"].invite_service.create_grant(db, payload, user)


@router.delete("/grants/{grant_id}", response_model=InviteGrantOut)
def revoke_invite_grant(
    grant_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("users:write")),
) -> InviteQuotaGrant:
    return db.info["container"].invite_service.revoke_grant(db, grant_id, user)


@router.get("/summary/me", response_model=InviteSummaryOut)
def get_my_invite_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("users:read")),
) -> InviteSummaryOut:
    return db.info["container"].invite_service.get_summary(db, "USER", user.id)


@router.get("/summary/groups/{group_id}", response_model=InviteSummaryOut)
def get_group_invite_summary(
    group_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:read")),
) -> InviteSummaryOut:
    return db.info["container"].invite_service.get_summary(db, "GROUP", group_id)


@router.post("/{code}/redeem", response_model=InviteRedeemResult)
def redeem_invite(
    code: str,
    payload: InviteRedeemRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> InviteRedeemResult:
    return db.info["container"].invite_service.redeem_invite(db, code, payload)
