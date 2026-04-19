import pytest
from fastapi import WebSocketException
from sqlalchemy import select

from app.models import ActionDispatch, Cocoon, Message, SessionState


class _DummyWebSocket:
    def __init__(self, access_token: str | None = None) -> None:
        self.query_params = {"access_token": access_token} if access_token else {}
        self.headers: dict[str, str] = {}
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True


def test_cocoon_tree_service_builds_nested_tree(client, auth_headers):
    container = client.app.state.container
    character_id = client.get("/api/v1/characters", headers=auth_headers).json()[0]["id"]
    model_id = client.get("/api/v1/providers/models", headers=auth_headers).json()[0]["id"]

    parent = client.post(
        "/api/v1/cocoons",
        headers=auth_headers,
        json={"name": "Parent", "character_id": character_id, "selected_model_id": model_id},
    ).json()
    child = client.post(
        "/api/v1/cocoons",
        headers=auth_headers,
        json={
            "name": "Child",
            "character_id": character_id,
            "selected_model_id": model_id,
            "parent_id": parent["id"],
        },
    ).json()

    with container.session_factory() as session:
        nodes = list(session.scalars(select(Cocoon).order_by(Cocoon.created_at.asc())).all())
        tree = container.cocoon_tree_service.build_tree(nodes)

    parent_node = next(node for node in tree if node.id == parent["id"])
    assert parent_node.children[0].id == child["id"]


def test_message_dispatch_service_enqueues_chat_round(client, default_cocoon_id):
    container = client.app.state.container
    with container.session_factory() as session:
        action = container.message_dispatch_service.enqueue_chat_message(
            session,
            default_cocoon_id,
            content="Service-level chat dispatch",
            client_request_id="svc-chat-1",
            timezone="UTC",
        )

    with container.session_factory() as session:
        action = session.get(ActionDispatch, action.id)
        message = session.scalar(select(Message).where(Message.client_request_id == "svc-chat-1"))
        state = session.get(SessionState, default_cocoon_id)
        assert action is not None
        assert action.event_type == "chat"
        assert message is not None
        assert message.content == "Service-level chat dispatch"
        assert state is not None


def test_message_dispatch_commits_before_enqueuing(client, default_cocoon_id, monkeypatch):
    container = client.app.state.container
    seen: dict[str, str | None] = {"action_id": None}
    original_enqueue = container.chat_queue.enqueue

    def enqueue_and_verify(action_id: str, cocoon_id: str, event_type: str, payload: dict) -> int:
        with container.session_factory() as verification_session:
            persisted = verification_session.get(ActionDispatch, action_id)
            assert persisted is not None
            seen["action_id"] = persisted.id
        return original_enqueue(action_id, cocoon_id, event_type, payload)

    monkeypatch.setattr(container.chat_queue, "enqueue", enqueue_and_verify)

    with container.session_factory() as session:
        action = container.message_dispatch_service.enqueue_chat_message(
            session,
            default_cocoon_id,
            content="Race-condition check",
            client_request_id="svc-chat-race",
            timezone="UTC",
        )

    assert seen["action_id"] == action.id


def test_cocoon_tag_service_updates_session_tags(client, default_cocoon_id):
    container = client.app.state.container
    with container.session_factory() as session:
        binding = container.cocoon_tag_service.bind_tag(session, default_cocoon_id, "focus")
        session.commit()
        binding_id = binding.id

    with container.session_factory() as session:
        state = session.get(SessionState, default_cocoon_id)
        assert state is not None
        assert "focus" in state.active_tags_json
        assert binding_id


def test_workspace_realtime_service_requires_token(client):
    container = client.app.state.container
    websocket = _DummyWebSocket()

    with pytest.raises(WebSocketException):
        import asyncio

        asyncio.run(
            container.workspace_realtime_service.connect_authenticated(
                websocket,
                "missing-cocoon",
                "cocoons:read",
            )
        )
