"""Invite-code administration service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import InviteCode, InviteQuotaGrant, User, UserGroup
from app.schemas.access.invites import InviteCreate, InviteGrantCreate, InviteRedeemRequest


@dataclass(slots=True)
class InviteSummary:
    target_type: str
    target_id: str
    invite_quota_remaining: int
    invite_quota_unlimited: bool


class InviteService:
    """Creates invite codes, manages grants, and resolves quota summaries."""

    def list_invites(self, session: Session) -> list[InviteCode]:
        """Return invites ordered by newest first."""
        return list(session.scalars(select(InviteCode).order_by(InviteCode.created_at.desc())).all())

    def list_grants(self, session: Session) -> list[InviteQuotaGrant]:
        """Return quota grants ordered by newest first."""
        return list(session.scalars(select(InviteQuotaGrant).order_by(InviteQuotaGrant.created_at.desc())).all())

    def create_invite(self, session: Session, payload: InviteCreate, user: User) -> InviteCode:
        """Create an invite code attributed to the acting user."""
        source_type = (payload.source_type or "ADMIN_OVERRIDE").upper()
        source_id = payload.source_id
        created_for_user_id = payload.created_for_user_id or user.id

        if source_type == "USER":
            source_id = source_id or user.id
            self._ensure_user_exists(session, source_id)
            summary = self.get_summary(session, "USER", source_id)
            if not summary.invite_quota_unlimited and summary.invite_quota_remaining < payload.quota_total:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite quota exceeded")
        elif source_type == "GROUP":
            if not source_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group source_id is required")
            self._ensure_group_exists(session, source_id)
            summary = self.get_summary(session, "GROUP", source_id)
            if not summary.invite_quota_unlimited and summary.invite_quota_remaining < payload.quota_total:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite quota exceeded")
        elif source_type != "ADMIN_OVERRIDE":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported invite source")

        invite = InviteCode(
            code=payload.code,
            quota_total=payload.quota_total,
            expires_at=payload.expires_at,
            created_by_user_id=user.id,
            created_for_user_id=created_for_user_id,
            source_type=source_type,
            source_id=source_id,
        )
        session.add(invite)
        session.flush()
        return invite

    def revoke_invite(self, session: Session, code: str) -> InviteCode:
        """Revoke an unused invite code so its quota becomes available again."""
        invite = self._get_invite_by_code(session, code)
        if invite.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite already revoked")
        if invite.quota_used > 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Used invites cannot be revoked")
        invite.revoked_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()
        return invite

    def create_grant(self, session: Session, payload: InviteGrantCreate, user: User) -> InviteQuotaGrant:
        """Create a quota grant that can later back invite-code creation."""
        target_type = payload.target_type.upper()
        if target_type == "USER":
            self._ensure_user_exists(session, payload.target_id)
        elif target_type == "GROUP":
            self._ensure_group_exists(session, payload.target_id)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported grant target")

        grant = InviteQuotaGrant(
            invite_code_id=None,
            granted_by_user_id=user.id,
            user_id=payload.target_id if target_type == "USER" else None,
            source_type="ADMIN_OVERRIDE",
            source_id=None,
            target_type=target_type,
            target_id=payload.target_id,
            quota=payload.amount,
            is_unlimited=payload.is_unlimited,
            note=payload.note,
        )
        session.add(grant)
        session.flush()
        return grant

    def get_summary(self, session: Session, target_type: str, target_id: str) -> InviteSummary:
        """Compute the current available invite quota for a user or group bucket."""
        normalized_type = target_type.upper()
        if normalized_type == "USER":
            self._ensure_user_exists(session, target_id)
        elif normalized_type == "GROUP":
            self._ensure_group_exists(session, target_id)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported summary target")

        unlimited = bool(
            session.scalar(
                select(func.count(InviteQuotaGrant.id)).where(
                    InviteQuotaGrant.target_type == normalized_type,
                    InviteQuotaGrant.target_id == target_id,
                    InviteQuotaGrant.is_unlimited.is_(True),
                )
            )
        )
        total_granted = session.scalar(
            select(func.coalesce(func.sum(InviteQuotaGrant.quota), 0)).where(
                InviteQuotaGrant.target_type == normalized_type,
                InviteQuotaGrant.target_id == target_id,
                InviteQuotaGrant.is_unlimited.is_(False),
            )
        ) or 0
        total_consumed = session.scalar(
            select(func.coalesce(func.sum(InviteCode.quota_total), 0)).where(
                InviteCode.source_type == normalized_type,
                InviteCode.source_id == target_id,
                InviteCode.revoked_at.is_(None),
            )
        ) or 0
        remaining = max(int(total_granted) - int(total_consumed), 0)
        return InviteSummary(
            target_type=normalized_type,
            target_id=target_id,
            invite_quota_remaining=remaining,
            invite_quota_unlimited=unlimited,
        )

    def redeem_invite(self, session: Session, code: str, payload: InviteRedeemRequest) -> dict:
        """Redeem quota from an invite code into a user grant."""
        invite = self._get_invite_by_code(session, code)
        if invite.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite revoked")
        if invite.expires_at and invite.expires_at < datetime.now(UTC).replace(tzinfo=None):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite expired")
        if invite.quota_used + payload.quota > invite.quota_total:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite quota exceeded")

        self._ensure_user_exists(session, payload.user_id)

        grant = InviteQuotaGrant(
            invite_code_id=invite.id,
            granted_by_user_id=invite.created_by_user_id,
            user_id=payload.user_id,
            source_type=invite.source_type,
            source_id=invite.source_id,
            target_type="USER",
            target_id=payload.user_id,
            quota=payload.quota,
            is_unlimited=False,
            note=f"Redeemed from invite code {invite.code}",
        )
        invite.quota_used += payload.quota
        session.add(grant)
        session.flush()
        return {"invite_code_id": invite.id, "grant_id": grant.id, "quota_used": invite.quota_used}

    def _get_invite_by_code(self, session: Session, code: str) -> InviteCode:
        invite = session.scalar(select(InviteCode).where(InviteCode.code == code))
        if not invite:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
        return invite

    def _ensure_user_exists(self, session: Session, user_id: str) -> None:
        if not session.get(User, user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    def _ensure_group_exists(self, session: Session, group_id: str) -> None:
        if not session.get(UserGroup, group_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
