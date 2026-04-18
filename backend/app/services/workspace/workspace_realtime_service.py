"""Workspace websocket access and connection orchestration."""

from __future__ import annotations

from fastapi import WebSocket, WebSocketException, status
from sqlalchemy.orm import sessionmaker, Session

from app.models import Cocoon
from app.services.realtime.connection_manager import ConnectionManager
from app.services.security.authorization_service import AuthorizationService
from app.services.security.token_authentication_service import TokenAuthenticationService


def _extract_bearer_token(raw_authorization: str | None) -> str | None:
    """Return the bearer token from an Authorization header when present."""
    if not raw_authorization:
        return None
    scheme, _, token = raw_authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


class WorkspaceRealtimeService:
    """Handles authenticated cocoon websocket connection setup and teardown."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        token_authentication_service: TokenAuthenticationService,
        authorization_service: AuthorizationService,
        connection_manager: ConnectionManager,
    ) -> None:
        self.session_factory = session_factory
        self.token_authentication_service = token_authentication_service
        self.authorization_service = authorization_service
        self.connection_manager = connection_manager

    def _extract_token(self, websocket: WebSocket) -> str:
        token = websocket.query_params.get("access_token") or _extract_bearer_token(
            websocket.headers.get("authorization")
        )
        if not token:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Missing bearer token",
            )
        return token

    async def connect_authenticated(self, websocket: WebSocket, cocoon_id: str, permission: str) -> None:
        """Authenticate websocket access, ensure cocoon exists, and connect it."""
        token = self._extract_token(websocket)
        with self.session_factory() as session:
            user = self.token_authentication_service.resolve_active_websocket_user(session, token)
            self.token_authentication_service.require_user_permission(session, user, permission)
            self.authorization_service.require_cocoon_access(session, user, cocoon_id, write=False)
        await self.connection_manager.connect(cocoon_id, websocket)

    def disconnect(self, cocoon_id: str, websocket: WebSocket) -> None:
        """Disconnect a cocoon websocket."""
        self.connection_manager.disconnect(cocoon_id, websocket)
