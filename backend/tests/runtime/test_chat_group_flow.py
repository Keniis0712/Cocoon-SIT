from sqlalchemy import select

from app.models import ActionDispatch, AuditRun, ChatGroupRoom, Message


def test_chat_group_flow_with_websocket(client, worker_runtime, auth_headers):
    character_id = client.get("/api/v1/characters", headers=auth_headers).json()[0]["id"]
    model_id = client.get("/api/v1/providers/models", headers=auth_headers).json()[0]["id"]
    room_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={
            "name": "Runtime Group",
            "character_id": character_id,
            "selected_model_id": model_id,
        },
    )
    assert room_response.status_code == 200, room_response.text
    room_id = room_response.json()["id"]

    access_token = auth_headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/api/v1/chat-groups/{room_id}/ws?access_token={access_token}") as websocket:
        response = client.post(
            f"/api/v1/chat-groups/{room_id}/messages",
            headers=auth_headers,
            json={
                "content": "Hello from the group room",
                "client_request_id": "room-req-1",
                "timezone": "UTC",
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
        assert any(item["type"] == "reply_started" for item in seen)
        assert any(item["type"] == "reply_done" for item in seen)

    messages = client.get(f"/api/v1/chat-groups/{room_id}/messages", headers=auth_headers)
    assert messages.status_code == 200, messages.text
    payload = messages.json()
    user_message = next(item for item in payload if item["role"] == "user")
    assert user_message["sender_user_id"] is not None
    assert any(item["role"] == "assistant" for item in payload)

    retract = client.post(
        f"/api/v1/chat-groups/{room_id}/messages/{user_message['id']}/retract",
        headers=auth_headers,
    )
    assert retract.status_code == 200, retract.text
    assert retract.json()["is_retracted"] is True

    after_retract = client.get(f"/api/v1/chat-groups/{room_id}/messages", headers=auth_headers)
    assert after_retract.status_code == 200, after_retract.text
    user_message = next(item for item in after_retract.json() if item["id"] == user_message["id"])
    assert user_message["content"] == "[message retracted]"
    assert user_message["is_retracted"] is True

    with client.app.state.container.session_factory() as session:
        room = session.get(ChatGroupRoom, room_id)
        action = session.get(ActionDispatch, action_id)
        audit_runs = list(session.scalars(select(AuditRun).where(AuditRun.action_id == action_id)).all())
        stored_message = session.scalar(select(Message).where(Message.client_request_id == "room-req-1"))
        assert room is not None
        assert action is not None
        assert action.chat_group_id == room_id
        assert audit_runs and audit_runs[0].chat_group_id == room_id
        assert stored_message is not None and stored_message.content == "Hello from the group room"
