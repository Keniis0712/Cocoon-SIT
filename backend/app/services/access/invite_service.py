"""Invite-code administration service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InviteCode, InviteQuotaAccount, InviteQuotaGrant, Role, User, UserGroup
from app.schemas.access.invites import InviteCreate, InviteGrantCreate, InviteQuotaUpdate, InviteRedeemRequest
from app.services.access.group_service import GroupService


@dataclass(slots=True)
class InviteSummary:
    target_type: str
    target_id: str
    invite_quota_remaining: int
    invite_quota_unlimited: bool


class InviteService:
    """Creates invite codes, manages grants, and resolves quota summaries."""

    _CODE_SUFFIX_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    _CODE_SUFFIX_LENGTH = 8

    def __init__(self, group_service: GroupService | None = None) -> None:
        self.group_service = group_service or GroupService()

    def list_invites(self, session: Session) -> list[InviteCode]:
        """Return invites ordered by newest first."""
        return list(session.scalars(select(InviteCode).order_by(InviteCode.created_at.desc())).all())

    def list_grants(self, session: Session) -> list[InviteQuotaGrant]:
        """Return quota grants ordered by newest first."""
        return list(session.scalars(select(InviteQuotaGrant).order_by(InviteQuotaGrant.created_at.desc())).all())

    def list_quota_accounts(self, session: Session) -> list[InviteQuotaAccount]:
        """Return direct quota balances ordered by target type then recency."""
        return list(
            session.scalars(
                select(InviteQuotaAccount).order_by(
                    InviteQuotaAccount.target_type.asc(),
                    InviteQuotaAccount.updated_at.desc(),
                )
            ).all()
        )

    def create_invite(self, session: Session, payload: InviteCreate, user: User) -> InviteCode:
        """Create an invite code attributed to the acting user."""
        source_type = (payload.source_type or "ADMIN_OVERRIDE").upper()
        source_id = payload.source_id
        created_for_user_id = payload.created_for_user_id or user.id
        invite_code = payload.code or self._generate_invite_code(session, payload.prefix)
        registration_group = session.get(UserGroup, payload.registration_group_id)
        if not registration_group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration group not found")

        if payload.expires_at is None and not self._is_admin(session, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can create permanent invites",
            )

        if source_type == "USER":
            source_id = source_id or user.id
            self._ensure_user_exists(session, source_id)
            summary = self.get_summary(session, "USER", source_id)
            if not summary.invite_quota_unlimited and summary.invite_quota_remaining < payload.quota_total:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite quota exceeded")
            self._consume_quota(session, "USER", source_id, payload.quota_total)
        elif source_type == "GROUP":
            if not source_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group source_id is required")
            self._ensure_group_exists(session, source_id)
            summary = self.get_summary(session, "GROUP", source_id)
            if not summary.invite_quota_unlimited and summary.invite_quota_remaining < payload.quota_total:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite quota exceeded")
            self._consume_quota(session, "GROUP", source_id, payload.quota_total)
        elif source_type != "ADMIN_OVERRIDE":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported invite source")

        invite = InviteCode(
            code=invite_code,
            quota_total=payload.quota_total,
            expires_at=payload.expires_at,
            created_by_user_id=user.id,
            created_for_user_id=created_for_user_id,
            registration_group_id=registration_group.id,
            source_type=source_type,
            source_id=source_id,
        )
        session.add(invite)
        session.flush()
        return invite

    def revoke_invite(self, session: Session, code: str) -> InviteCode:
        """Revoke an unused invite code so future registrations cannot consume it."""
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
            revoked_at=None,
        )
        session.add(grant)
        account = self._get_or_create_account(session, target_type, payload.target_id)
        if payload.is_unlimited:
            account.is_unlimited = True
        else:
            account.remaining_quota += int(payload.amount)
        session.flush()
        return grant

    def revoke_grant(self, session: Session, grant_id: str, user: User) -> InviteQuotaGrant:
        """Revoke an existing quota grant so it no longer contributes future invite capacity."""
        if not self._is_admin(session, user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can revoke invite grants")
        grant = session.get(InviteQuotaGrant, grant_id)
        if not grant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite grant not found")
        if grant.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite grant already revoked")
        grant.revoked_at = datetime.now(UTC).replace(tzinfo=None)
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

        account = self._get_or_create_account(session, normalized_type, target_id)
        return InviteSummary(
            target_type=normalized_type,
            target_id=target_id,
            invite_quota_remaining=max(int(account.remaining_quota), 0),
            invite_quota_unlimited=bool(account.is_unlimited),
        )

    def update_summary(
        self,
        session: Session,
        target_type: str,
        target_id: str,
        payload: InviteQuotaUpdate,
        user: User,
    ) -> InviteSummary:
        """Directly update the current quota balance for a user or group bucket."""
        if not self._is_admin(session, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can update invite quota balances",
            )

        normalized_type = target_type.upper()
        if normalized_type == "USER":
            self._ensure_user_exists(session, target_id)
        elif normalized_type == "GROUP":
            self._ensure_group_exists(session, target_id)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported summary target")

        account = self._get_or_create_account(session, normalized_type, target_id)
        if payload.invite_quota_remaining is not None:
            account.remaining_quota = max(int(payload.invite_quota_remaining), 0)
        if payload.invite_quota_unlimited is not None:
            account.is_unlimited = bool(payload.invite_quota_unlimited)
        session.flush()
        return self.get_summary(session, normalized_type, target_id)

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
            revoked_at=None,
        )
        invite.quota_used += payload.quota
        session.add(grant)
        account = self._get_or_create_account(session, "USER", payload.user_id)
        account.remaining_quota += int(payload.quota)
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

    def _generate_invite_code(self, session: Session, prefix: str | None) -> str:
        normalized_prefix = self._normalize_prefix(prefix)
        for _ in range(20):
            suffix = "".join(
                secrets.choice(self._CODE_SUFFIX_ALPHABET)
                for _ in range(self._CODE_SUFFIX_LENGTH)
            )
            code = f"{normalized_prefix}-{suffix}"
            if session.scalar(select(InviteCode.id).where(InviteCode.code == code)) is None:
                return code

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate unique invite code",
        )

    def _normalize_prefix(self, prefix: str | None) -> str:
        raw_prefix = (prefix or "INVITE").strip().upper()
        normalized = re.sub(r"[^A-Z0-9]+", "-", raw_prefix).strip("-")
        if not normalized:
            normalized = "INVITE"
        max_prefix_length = 64 - self._CODE_SUFFIX_LENGTH - 1
        return normalized[:max_prefix_length]

    def _is_admin(self, session: Session, user: User) -> bool:
        if not user.role_id:
            return False
        role = session.get(Role, user.role_id)
        return bool(role and role.name == "admin")

    def _get_or_create_account(self, session: Session, target_type: str, target_id: str) -> InviteQuotaAccount:
        account = session.scalar(
            select(InviteQuotaAccount).where(
                InviteQuotaAccount.target_type == target_type,
                InviteQuotaAccount.target_id == target_id,
            )
        )
        if account:
            return account
        account = InviteQuotaAccount(
            target_type=target_type,
            target_id=target_id,
            remaining_quota=0,
            is_unlimited=False,
        )
        session.add(account)
        session.flush()
        return account

    def _consume_quota(self, session: Session, target_type: str, target_id: str, amount: int) -> None:
        account = self._get_or_create_account(session, target_type, target_id)
        if account.is_unlimited:
            return
        remaining = int(account.remaining_quota or 0)
        if remaining < amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite quota exceeded")
        account.remaining_quota = remaining - int(amount)
