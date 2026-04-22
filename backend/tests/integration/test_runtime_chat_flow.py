import pytest
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import select

from app.models import ActionDispatch, AuditRun, Message

pytestmark = pytest.mark.integration


def test_chat_flow_with_websocket(client, worker_runtime, auth_headers, default_cocoon_id):
    access_token = auth_headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(
        f"/api/v1/cocoons/{default_cocoon_id}/ws?access_token={access_token}"
    ) as websocket:
        response = client.post(
            f"/api/v1/cocoons/{default_cocoon_id}/messages",
            headers=auth_headers,
            json={
                "content": "Hello from the test harness",
                "client_request_id": "req-1",
                "timezone": "Asia/Shanghai",
            },
        )
        assert response.status_code == 202, response.text
        action_id = response.json()["action_id"]

        queued_event = websocket.receive_json()
        assert queued_event["type"] == "dispatch_queued"
        assert queued_event["action_id"] == action_id

        assert worker_runtime.process_next_chat_dispatch() is True

        seen = []
        for _ in range(20):
            event = websocket.receive_json()
            seen.append(event)
            if event["type"] == "reply_done":
                break
        event_types = [item["type"] for item in seen]
        assert "state_patch" in event_types
        assert "reply_started" in event_types
        assert "reply_done" in event_types
        assert any(item["type"] == "reply_chunk" for item in seen)

    messages = client.get(f"/api/v1/cocoons/{default_cocoon_id}/messages", headers=auth_headers).json()
    assert any(message["role"] == "assistant" for message in messages)

    with client.app.state.container.session_factory() as session:
        action = session.get(ActionDispatch, action_id)
        assert action is not None
        assert action.status == "completed"
        audit_runs = list(session.scalars(select(AuditRun).where(AuditRun.action_id == action_id)).all())
        assert audit_runs

    detail = client.get(f"/api/v1/audits/{audit_runs[0].id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    artifacts = detail.json()["artifacts"]
    generator_output = next(item for item in artifacts if item["kind"] == "generator_output")
    assert generator_output["payload_json"]["content"]
    meta_output = next(item for item in artifacts if item["kind"] == "meta_output")
    assert meta_output["payload_json"]["decision"] in {"reply", "silence"}


def test_websocket_requires_authentication(client, default_cocoon_id):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/cocoons/{default_cocoon_id}/ws") as websocket:
            websocket.receive_text()


def test_client_request_id_is_idempotent(client, auth_headers, default_cocoon_id):
    payload = {
        "content": "Deduplicate this message",
        "client_request_id": "req-idem",
        "timezone": "UTC",
    }
    first = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json=payload,
    )
    second = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json=payload,
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["action_id"] == second.json()["action_id"]

    with client.app.state.container.session_factory() as session:
        messages = list(
            session.scalars(
                select(Message).where(Message.client_request_id == payload["client_request_id"])
            ).all()
        )
        assert len(messages) == 1
