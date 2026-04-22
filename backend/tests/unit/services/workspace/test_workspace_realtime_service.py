import pytest
from fastapi import WebSocketException

from app.services.workspace.workspace_realtime_service import (
    WorkspaceRealtimeService,
    _extract_bearer_token,
)


class _SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


class _WebSocket:
    def __init__(self, *, query_params=None, headers=None):
        self.query_params = query_params or {}
        self.headers = headers or {}


@pytest.mark.asyncio
async def test_workspace_realtime_service_connects_cocoon_and_chat_group_targets():
    connections = []
    cocoon_access = []
    room_access = []
    permission_calls = []
    session = object()
    user = object()

    class _ConnectionManager:
        async def connect(self, channel_key, websocket):
            connections.append((channel_key, websocket))

        def disconnect(self, channel_key, websocket):
            connections.append(("disconnect", channel_key, websocket))

    service = WorkspaceRealtimeService(
        session_factory=lambda: _SessionContext(session),
        token_authentication_service=type(
            "_TokenAuth",
            (),
            {
                "resolve_active_websocket_user": lambda self, current_session, token: user,
                "require_user_permission": lambda self, current_session, current_user, permission: permission_calls.append(
                    (current_session, current_user, permission)
                ),
            },
        )(),
        authorization_service=type(
            "_Authorization",
            (),
            {
                "require_cocoon_access": lambda self, current_session, current_user, target_id, write=False: cocoon_access.append(
                    (current_session, current_user, target_id, write)
                ),
                "require_chat_group_access": lambda self, current_session, current_user, target_id: room_access.append(
                    (current_session, current_user, target_id)
                ),
            },
        )(),
        connection_manager=_ConnectionManager(),
    )

    cocoon_socket = _WebSocket(query_params={"access_token": "token-1"})
    chat_group_socket = _WebSocket(headers={"authorization": "Bearer token-2"})

    await service.connect_authenticated(cocoon_socket, "cocoon-1", "workspace:read")
    await service.connect_authenticated(
        chat_group_socket,
        "group-1",
        "workspace:read",
        target_type="chat_group",
    )
    service.disconnect("cocoon-1", cocoon_socket)
    service.disconnect("group-1", chat_group_socket, target_type="chat_group")

    assert permission_calls == [(session, user, "workspace:read"), (session, user, "workspace:read")]
    assert cocoon_access == [(session, user, "cocoon-1", False)]
    assert room_access == [(session, user, "group-1")]
    assert connections[0][0] == "cocoon:cocoon-1"
    assert connections[1][0] == "chat_group:group-1"
    assert connections[2] == ("disconnect", "cocoon:cocoon-1", cocoon_socket)
    assert connections[3] == ("disconnect", "chat_group:group-1", chat_group_socket)


def test_workspace_realtime_service_token_helpers():
    assert _extract_bearer_token(None) is None
    assert _extract_bearer_token("Basic abc") is None
    assert _extract_bearer_token("Bearer good-token") == "good-token"

    service = WorkspaceRealtimeService(
        session_factory=lambda: _SessionContext(object()),
        token_authentication_service=object(),
        authorization_service=object(),
        connection_manager=object(),
    )
    assert service._extract_token(_WebSocket(query_params={"access_token": "query-token"})) == "query-token"
    assert service._extract_token(_WebSocket(headers={"authorization": "Bearer header-token"})) == "header-token"

    with pytest.raises(WebSocketException) as exc_info:
        service._extract_token(_WebSocket())
    assert exc_info.value.reason == "Missing bearer token"
