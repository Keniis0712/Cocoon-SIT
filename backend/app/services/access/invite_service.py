"""Invite-code administration service."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InviteCode, InviteQuotaGrant, User
from app.schemas.access.invites import InviteCreate, InviteRedeemRequest


class InviteService:
    """Creates invite codes and redeems quota grants."""

    def list_invites(self, session: Session) -> list[InviteCode]:
        """Return invites ordered by newest first."""
        return list(session.scalars(select(InviteCode).order_by(InviteCode.created_at.desc())).all())

    def create_invite(self, session: Session, payload: InviteCreate, user: User) -> InviteCode:
        """Create an invite code attributed to the acting user."""
        invite = InviteCode(
            code=payload.code,
            quota_total=payload.quota_total,
            expires_at=payload.expires_at,
            created_by_user_id=user.id,
        )
        session.add(invite)
        session.flush()
        return invite

    def redeem_invite(self, session: Session, code: str, payload: InviteRedeemRequest) -> dict:
        """Redeem quota from an invite code into a user grant."""
        invite = session.scalar(select(InviteCode).where(InviteCode.code == code))
        if not invite:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
        if invite.expires_at and invite.expires_at < datetime.now(UTC).replace(tzinfo=None):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite expired")
        if invite.quota_used + payload.quota > invite.quota_total:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite quota exceeded")
        grant = InviteQuotaGrant(invite_code_id=invite.id, user_id=payload.user_id, quota=payload.quota)
        invite.quota_used += payload.quota
        session.add(grant)
        session.flush()
        return {"invite_code_id": invite.id, "grant_id": grant.id, "quota_used": invite.quota_used}
