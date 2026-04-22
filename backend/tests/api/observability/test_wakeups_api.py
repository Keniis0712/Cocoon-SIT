from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import WakeupTask
from app.models.entities import DurableJobStatus


def _unwrap(response):
    payload = response.json()
    if isinstance(payload, dict) and {"code", "msg", "data"} <= set(payload.keys()):
        return payload["data"]
    return payload


def _default_character_and_model_ids(client, auth_headers):
    characters = _unwrap(client.get("/api/v1/characters", headers=auth_headers))
    models = _unwrap(client.get("/api/v1/providers/models", headers=auth_headers))
    return characters[0]["id"], models[0]["id"]


def test_workspace_and_audit_wakeup_routes_return_reasonful_ai_wakeups(client, auth_headers, default_cocoon_id):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_room = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={"name": "Wakeup Audit Room", "character_id": character_id, "selected_model_id": model_id},
    )
    assert create_room.status_code == 200, create_room.text
    room_id = _unwrap(create_room)["id"]

    now = datetime.now(UTC).replace(tzinfo=None)
    with container.session_factory() as session:
        session.add_all(
            [
                WakeupTask(
                    cocoon_id=default_cocoon_id,
                    run_at=now + timedelta(minutes=5),
                    reason="Check in after the user had time to respond",
                    status=DurableJobStatus.queued,
                    payload_json={"scheduled_by": "meta_node"},
                ),
                WakeupTask(
                    cocoon_id=default_cocoon_id,
                    run_at=now + timedelta(minutes=10),
                    reason="Idle timeout follow-up",
                    status=DurableJobStatus.queued,
                    payload_json={"scheduled_by": "idle_timeout_default", "trigger_kind": "idle_timeout"},
                ),
                WakeupTask(
                    chat_group_id=room_id,
                    run_at=now + timedelta(minutes=15),
                    reason="Revisit the group plan after lunch",
                    status=DurableJobStatus.queued,
                    payload_json={"scheduled_by": "meta_node"},
                ),
            ]
        )
        session.commit()

    cocoon_response = client.get(
        f"/api/v1/cocoons/{default_cocoon_id}/wakeups",
        headers=auth_headers,
        params={"status": DurableJobStatus.queued, "only_ai": "true"},
    )
    assert cocoon_response.status_code == 200, cocoon_response.text
    cocoon_payload = _unwrap(cocoon_response)
    assert len(cocoon_payload) == 1
    assert cocoon_payload[0]["is_ai_wakeup"] is True
    assert cocoon_payload[0]["reason"] == "Check in after the user had time to respond"
    assert cocoon_payload[0]["target_type"] == "cocoon"

    room_response = client.get(
        f"/api/v1/chat-groups/{room_id}/wakeups",
        headers=auth_headers,
        params={"status": DurableJobStatus.queued, "only_ai": "true"},
    )
    assert room_response.status_code == 200, room_response.text
    room_payload = _unwrap(room_response)
    assert len(room_payload) == 1
    assert room_payload[0]["reason"] == "Revisit the group plan after lunch"
    assert room_payload[0]["target_type"] == "chat_group"

    audit_response = client.get(
        "/api/v1/audits/wakeups",
        headers=auth_headers,
        params={"status": DurableJobStatus.queued, "only_ai": "true", "limit": 10},
    )
    assert audit_response.status_code == 200, audit_response.text
    audit_payload = _unwrap(audit_response)
    assert len(audit_payload) == 2
    assert {item["target_type"] for item in audit_payload} == {"cocoon", "chat_group"}
    assert all(item["is_ai_wakeup"] for item in audit_payload)
    assert all(item["reason"] for item in audit_payload)


def test_audit_wakeup_route_supports_target_filtering(client, auth_headers):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_room = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={"name": "Wakeup Filter Room", "character_id": character_id, "selected_model_id": model_id},
    )
    assert create_room.status_code == 200, create_room.text
    room_id = _unwrap(create_room)["id"]

    now = datetime.now(UTC).replace(tzinfo=None)
    with container.session_factory() as session:
        session.add(
            WakeupTask(
                chat_group_id=room_id,
                run_at=now + timedelta(minutes=20),
                reason="Filter me",
                status=DurableJobStatus.cancelled,
                payload_json={"scheduled_by": "meta_node", "cancelled_reason": "superseded"},
                cancelled_at=now,
            )
        )
        session.commit()

    response = client.get(
        "/api/v1/audits/wakeups",
        headers=auth_headers,
        params={"target_type": "chat_group", "target_id": room_id, "limit": 10},
    )
    assert response.status_code == 200, response.text
    payload = _unwrap(response)
    assert len(payload) == 1
    assert payload[0]["target_id"] == room_id
    assert payload[0]["cancelled_reason"] == "superseded"
    assert payload[0]["target_name"] == "Wakeup Filter Room"
