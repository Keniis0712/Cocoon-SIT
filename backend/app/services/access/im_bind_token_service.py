from __future__ import annotations

from datetime import UTC, datetime, timedelta
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserImBindToken
from app.services.security.encryption import hash_secret, verify_secret


class ImBindTokenService:
    def __init__(self, *, ttl_seconds: int = 60) -> None:
        self.ttl_seconds = ttl_seconds

    def issue_for_user(self, session: Session, user: User) -> tuple[str, UserImBindToken]:
        now = self._now()
        self._revoke_active_tokens(session, user.id, now)
        self._prune_expired_tokens(session, now)

        token = secrets.token_urlsafe(9)
        row = UserImBindToken(
            user_id=user.id,
            token_hash=hash_secret(token),
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )
        session.add(row)
        session.flush()
        return token, row

    def verify_user_token(self, session: Session, *, username: str, token: str) -> User:
        normalized_username = username.strip()
        normalized_token = token.strip()
        if not normalized_username or not normalized_token:
            raise ValueError("username and token are required")

        user = session.scalar(select(User).where(User.username == normalized_username))
        if not user or not user.is_active:
            raise ValueError("invalid username or token")

        now = self._now()
        self._prune_expired_tokens(session, now)

        candidates = list(
            session.scalars(
                select(UserImBindToken)
                .where(
                    UserImBindToken.user_id == user.id,
                    UserImBindToken.revoked_at.is_(None),
                    UserImBindToken.expires_at > now,
                )
                .order_by(UserImBindToken.created_at.desc())
            ).all()
        )
        for row in candidates:
            if verify_secret(normalized_token, row.token_hash):
                row.last_validated_at = now
                session.flush()
                return user
        raise ValueError("invalid username or token")

    def _revoke_active_tokens(self, session: Session, user_id: str, now: datetime) -> None:
        rows = session.scalars(
            select(UserImBindToken).where(
                UserImBindToken.user_id == user_id,
                UserImBindToken.revoked_at.is_(None),
                UserImBindToken.expires_at > now,
            )
        ).all()
        for row in rows:
            row.revoked_at = now
            row.updated_at = now

    def _prune_expired_tokens(self, session: Session, now: datetime) -> None:
        rows = session.scalars(
            select(UserImBindToken).where(
                UserImBindToken.revoked_at.is_(None),
                UserImBindToken.expires_at <= now,
            )
        ).all()
        for row in rows:
            row.revoked_at = now
            row.updated_at = now

    def _now(self) -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)
