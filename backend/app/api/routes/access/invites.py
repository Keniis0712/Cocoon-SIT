from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import InviteCode, User
from app.schemas.access.invites import InviteCreate, InviteOut, InviteRedeemRequest, InviteRedeemResult


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


@router.post("/{code}/redeem", response_model=InviteRedeemResult)
def redeem_invite(
    code: str,
    payload: InviteRedeemRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> InviteRedeemResult:
    return db.info["container"].invite_service.redeem_invite(db, code, payload)
