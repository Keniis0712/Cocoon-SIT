"""JWT token service used by REST and websocket authentication flows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.core.config import Settings


class TokenService:
    """Creates and validates signed access and refresh tokens."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_access_token(self, user_id: str) -> str:
        """Create a short-lived access token for API and websocket access."""
        expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.access_token_expire_minutes)
        return jwt.encode(
            {"sub": user_id, "exp": expires_at, "jti": uuid4().hex},
            self.settings.secret_key,
            algorithm="HS256",
        )

    def create_refresh_token(self, user_id: str) -> str:
        """Create a long-lived refresh token for session continuation."""
        expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.refresh_token_expire_minutes)
        return jwt.encode(
            {"sub": user_id, "typ": "refresh", "exp": expires_at, "jti": uuid4().hex},
            self.settings.secret_key,
            algorithm="HS256",
        )

    def decode_token(self, token: str) -> dict:
        """Decode and validate a signed JWT."""
        return jwt.decode(token, self.settings.secret_key, algorithms=["HS256"])
