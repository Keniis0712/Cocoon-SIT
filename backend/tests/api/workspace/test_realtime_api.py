from __future__ import annotations

import pytest
from fastapi import WebSocketException
from starlette.websockets import WebSocketDisconnect


def _chat_group_id(client, auth_headers: dict[str, str]) -> str:
    characters = client.get("/api/v1/characters", headers=auth_headers).json()
    models = client.get("/api/v1/providers/models", headers=auth_headers).json()
    response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={
            "name": "Realtime Group",
            "character_id": characters[0]["id"],
            "selected_model_id": models[0]["id"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_cocoon_ws_route_connects_and_disconnects(client, default_cocoon_id, monkeypatch):
    container = client.app.state.container
    calls: dict[str, tuple] = {}

    async def fake_connect_authenticated(websocket, target_id, permission, *, target_type):
        calls["connect"] = (target_id, permission, target_type)
        await websocket.accept()

    def fake_disconnect(target_id, websocket, *, target_type):
        calls["disconnect"] = (target_id, target_type)

    monkeypatch.setattr(container.workspace_realtime_service, "connect_authenticated", fake_connect_authenticated)
    monkeypatch.setattr(container.workspace_realtime_service, "disconnect", fake_disconnect)

    with client.websocket_connect(f"/api/v1/cocoons/{default_cocoon_id}/ws") as websocket:
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

    assert calls["connect"] == (default_cocoon_id, "cocoons:read", "cocoon")
    assert calls["disconnect"] == (default_cocoon_id, "cocoon")


def test_cocoon_ws_route_closes_when_authentication_fails(client, default_cocoon_id, monkeypatch):
    async def fake_connect_authenticated(*args, **kwargs):
        raise WebSocketException(code=4401)

    monkeypatch.setattr(
        client.app.state.container.workspace_realtime_service,
        "connect_authenticated",
        fake_connect_authenticated,
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/v1/cocoons/{default_cocoon_id}/ws"):
            pass

    assert exc_info.value.code == 4401


def test_chat_group_ws_route_connects_and_disconnects(client, auth_headers, monkeypatch):
    room_id = _chat_group_id(client, auth_headers)
    container = client.app.state.container
    calls: dict[str, tuple] = {}

    async def fake_connect_authenticated(websocket, target_id, permission, *, target_type):
        calls["connect"] = (target_id, permission, target_type)
        await websocket.accept()

    def fake_disconnect(target_id, websocket, *, target_type):
        calls["disconnect"] = (target_id, target_type)

    monkeypatch.setattr(container.workspace_realtime_service, "connect_authenticated", fake_connect_authenticated)
    monkeypatch.setattr(container.workspace_realtime_service, "disconnect", fake_disconnect)

    with client.websocket_connect(f"/api/v1/chat-groups/{room_id}/ws") as websocket:
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

    assert calls["connect"] == (room_id, "cocoons:read", "chat_group")
    assert calls["disconnect"] == (room_id, "chat_group")


def test_chat_group_ws_route_closes_when_authentication_fails(client, auth_headers, monkeypatch):
    room_id = _chat_group_id(client, auth_headers)

    async def fake_connect_authenticated(*args, **kwargs):
        raise WebSocketException(code=4403)

    monkeypatch.setattr(
        client.app.state.container.workspace_realtime_service,
        "connect_authenticated",
        fake_connect_authenticated,
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/v1/chat-groups/{room_id}/ws"):
            pass

    assert exc_info.value.code == 4403
