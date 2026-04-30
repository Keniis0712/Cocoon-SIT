from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.models import ActionDispatch, Cocoon, Message


def test_send_edit_and_retry_message_routes_enqueue_actions(client, auth_headers, default_cocoon_id):
    send_response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "Editable message",
            "client_request_id": "api-message-1",
            "timezone": "UTC",
        },
    )
    assert send_response.status_code == 202, send_response.text

    with client.app.state.container.session_factory() as session:
        message = session.scalar(select(Message).where(Message.client_request_id == "api-message-1"))
        assert message is not None
        message_id = message.id

    edit_response = client.patch(
        f"/api/v1/cocoons/{default_cocoon_id}/user_message",
        headers=auth_headers,
        json={"message_id": message_id, "content": "Edited content"},
    )
    assert edit_response.status_code == 202, edit_response.text

    retry_response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/reply/retry",
        headers=auth_headers,
        json={"message_id": message_id},
    )
    assert retry_response.status_code == 202, retry_response.text

    with client.app.state.container.session_factory() as session:
        actions = list(
            session.scalars(
                select(ActionDispatch)
                .where(ActionDispatch.cocoon_id == default_cocoon_id)
                .order_by(ActionDispatch.created_at.asc())
            ).all()
        )
        assert {item.event_type for item in actions} >= {"chat", "edit", "retry"}


def test_send_message_maps_dispatch_value_errors_to_404(client, auth_headers, default_cocoon_id, monkeypatch):
    container = client.app.state.container
    monkeypatch.setattr(
        container.message_dispatch_service,
        "enqueue_chat_message",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("dispatch target missing")),
    )

    response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "This should fail",
            "client_request_id": "api-message-fail",
            "timezone": "UTC",
        },
    )

    assert response.status_code == 404, response.text
    payload = response.json()
    assert payload["code"] == "DISPATCH_TARGET_MISSING"
    assert payload["msg"] == "dispatch target missing"
    assert payload["data"] is None


def test_edit_user_message_rejects_missing_or_non_user_messages(client, auth_headers, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        assistant_message = Message(cocoon_id=default_cocoon_id, role="assistant", content="Not editable")
        session.add(assistant_message)
        session.commit()
        assistant_message_id = assistant_message.id

    missing_response = client.patch(
        f"/api/v1/cocoons/{default_cocoon_id}/user_message",
        headers=auth_headers,
        json={"message_id": "missing-message", "content": "Edited"},
    )
    assert missing_response.status_code == 404, missing_response.text

    assistant_response = client.patch(
        f"/api/v1/cocoons/{default_cocoon_id}/user_message",
        headers=auth_headers,
        json={"message_id": assistant_message_id, "content": "Edited"},
    )
    assert assistant_response.status_code == 404, assistant_response.text


def test_list_messages_returns_serialized_messages(client, auth_headers, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        session.add_all(
            [
                Message(cocoon_id=default_cocoon_id, role="user", content="First listed message"),
                Message(cocoon_id=default_cocoon_id, role="assistant", content="Second listed message"),
            ]
        )
        session.commit()

    response = client.get(f"/api/v1/cocoons/{default_cocoon_id}/messages", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert [item["content"] for item in response.json()][-2:] == ["First listed message", "Second listed message"]


def test_child_cocoon_messages_include_parent_chain_history(client, auth_headers, create_branch_cocoon):
    container = client.app.state.container
    child_id = create_branch_cocoon("History Child")["id"]

    with container.session_factory() as session:
        child = session.get(Cocoon, child_id)
        assert child is not None
        assert child.parent_id is not None
        session.add_all(
            [
                Message(cocoon_id=child.parent_id, role="user", content="Parent history"),
                Message(cocoon_id=child_id, role="assistant", content="Child reply"),
            ]
        )
        session.commit()

    response = client.get(f"/api/v1/cocoons/{child_id}/messages", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert [item["content"] for item in response.json()][-2:] == ["Parent history", "Child reply"]


def test_list_messages_supports_reverse_window_loading(client, auth_headers, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        messages = [
            Message(
                id="api-window-1",
                cocoon_id=default_cocoon_id,
                role="user",
                content="Window first",
                created_at=datetime(2030, 1, 1, 10, 0, 0),
            ),
            Message(
                id="api-window-2",
                cocoon_id=default_cocoon_id,
                role="assistant",
                content="Window second",
                created_at=datetime(2030, 1, 1, 10, 1, 0),
            ),
            Message(
                id="api-window-3",
                cocoon_id=default_cocoon_id,
                role="user",
                content="Window third",
                created_at=datetime(2030, 1, 1, 10, 2, 0),
            ),
        ]
        session.add_all(messages)
        session.commit()

    latest_response = client.get(
        f"/api/v1/cocoons/{default_cocoon_id}/messages?limit=2",
        headers=auth_headers,
    )
    assert latest_response.status_code == 200, latest_response.text
    assert [item["content"] for item in latest_response.json()] == ["Window second", "Window third"]

    older_response = client.get(
        f"/api/v1/cocoons/{default_cocoon_id}/messages?before_message_id=api-window-3&limit=1",
        headers=auth_headers,
    )
    assert older_response.status_code == 200, older_response.text
    assert [item["content"] for item in older_response.json()] == ["Window second"]


def test_retry_route_exposes_debounce_timestamp_when_dispatch_sets_one(client, auth_headers, default_cocoon_id, monkeypatch):
    debounce_until = datetime.now(UTC) + timedelta(seconds=30)
    container = client.app.state.container

    monkeypatch.setattr(
        container.message_dispatch_service,
        "enqueue_retry",
        lambda *args, **kwargs: SimpleNamespace(id="retry-action", status="queued", debounce_until=debounce_until),
    )

    response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/reply/retry",
        headers=auth_headers,
        json={"message_id": "synthetic-message"},
    )

    assert response.status_code == 202, response.text
    assert response.json()["action_id"] == "retry-action"
    assert response.json()["debounce_until"] == int(debounce_until.timestamp())
