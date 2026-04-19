"""Workspace websocket access and connection orchestration."""

from __future__ import annotations

from fastapi import WebSocket, WebSocketException, status
from sqlalchemy.orm import sessionmaker, Session

from app.models import Cocoon
from app.services.realtime.connection_manager import ConnectionManager
from app.services.security.authorization_service import AuthorizationService
from app.services.security.token_authentication_service import TokenAuthenticationService
from app.services.workspace.targets import target_channel_key


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

    async def connect_authenticated(
        self,
        websocket: WebSocket,
        target_id: str,
        permission: str,
        *,
        target_type: str = "cocoon",
    ) -> None:
        """Authenticate websocket access, ensure the conversation target exists, and connect it."""
        token = self._extract_token(websocket)
        with self.session_factory() as session:
            user = self.token_authentication_service.resolve_active_websocket_user(session, token)
            self.token_authentication_service.require_user_permission(session, user, permission)
            if target_type == "cocoon":
                self.authorization_service.require_cocoon_access(session, user, target_id, write=False)
                channel_key = target_channel_key(cocoon_id=target_id)
            else:
                self.authorization_service.require_chat_group_access(session, user, target_id)
                channel_key = target_channel_key(chat_group_id=target_id)
        await self.connection_manager.connect(channel_key, websocket)

    def disconnect(self, target_id: str, websocket: WebSocket, *, target_type: str = "cocoon") -> None:
        """Disconnect a target websocket."""
        channel_key = (
            target_channel_key(cocoon_id=target_id)
            if target_type == "cocoon"
            else target_channel_key(chat_group_id=target_id)
        )
        self.connection_manager.disconnect(channel_key, websocket)
