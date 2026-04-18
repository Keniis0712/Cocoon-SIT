"""Token-driven user resolution helpers."""

from __future__ import annotations

from fastapi import HTTPException, WebSocketException, status
from sqlalchemy.orm import Session

from app.models import User
from app.services.security.rbac import require_permission
from app.services.security.token_service import TokenService


class TokenAuthenticationService:
    """Resolves active users from bearer tokens and enforces permissions."""

    def __init__(self, token_service: TokenService) -> None:
        self.token_service = token_service

    def resolve_active_user(self, session: Session, token: str) -> User:
        """Return the active user bound to a validated token."""
        try:
            payload = self.token_service.decode_token(token)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user = session.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        return user

    def resolve_active_websocket_user(self, session: Session, token: str) -> User:
        """Return the active user bound to a validated websocket token."""
        try:
            return self.resolve_active_user(session, token)
        except HTTPException as exc:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=exc.detail,
            ) from exc

    def require_user_permission(self, session: Session, user: User, permission: str) -> User:
        """Ensure the user owns the required permission and return it back."""
        require_permission(session, user, permission)
        return user
