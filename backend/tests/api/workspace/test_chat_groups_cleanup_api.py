from datetime import UTC, datetime

from sqlalchemy import select

from app.models import (
    ActionDispatch,
    AuditArtifact,
    AuditLink,
    AuditRun,
    AuditStep,
    ChatGroupRoom,
    DurableJob,
    FailedRound,
    MemoryChunk,
    Message,
    SessionState,
    WakeupTask,
)


def _default_character_and_model_ids(client, auth_headers):
    characters = client.get("/api/v1/characters", headers=auth_headers).json()
    models = client.get("/api/v1/providers/models", headers=auth_headers).json()
    return characters[0]["id"], models[0]["id"]


def _login_headers(client, username: str, password: str = "secret") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_delete_chat_group_cleans_related_records(client, auth_headers):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={"name": "Cleanup Group", "character_id": character_id, "selected_model_id": model_id},
    )
    assert create_response.status_code == 200, create_response.text
    room_id = create_response.json()["id"]

    with container.session_factory() as session:
        action = ActionDispatch(
            chat_group_id=room_id, event_type="chat", status="completed", payload_json={}
        )
        session.add(action)
        session.flush()

        message = Message(
            chat_group_id=room_id, action_id=action.id, role="assistant", content="Delete me"
        )
        session.add(message)
        session.flush()

        memory = MemoryChunk(
            chat_group_id=room_id,
            source_message_id=message.id,
            scope="dialogue",
            content="Delete memory",
        )
        session.add(memory)
        session.flush()

        job = DurableJob(
            chat_group_id=room_id, job_type="wakeup", lock_key="room-cleanup", payload_json={}
        )
        session.add(job)
        session.flush()
        session.add(
            WakeupTask(
                chat_group_id=room_id,
                run_at=datetime.now(UTC).replace(tzinfo=None),
                reason="room wakeup",
                payload_json={},
            )
        )

        run = AuditRun(chat_group_id=room_id, action_id=action.id, operation_type="chat")
        session.add(run)
        session.flush()
        step = AuditStep(run_id=run.id, step_name="generator")
        session.add(step)
        session.flush()
        artifact = AuditArtifact(
            run_id=run.id, step_id=step.id, kind="generator_output", metadata_json={}
        )
        session.add(artifact)
        session.flush()
        session.add(
            AuditLink(
                run_id=run.id,
                source_step_id=step.id,
                target_artifact_id=artifact.id,
                relation="produced_by",
            )
        )
        session.add(
            FailedRound(
                chat_group_id=room_id, action_id=action.id, event_type="chat", reason="cleanup"
            )
        )
        session.commit()

    delete_response = client.delete(f"/api/v1/chat-groups/{room_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["id"] == room_id

    with container.session_factory() as session:
        assert session.get(ChatGroupRoom, room_id) is None
        assert session.get(SessionState, room_id) is None
        assert session.scalar(select(Message).where(Message.chat_group_id == room_id)) is None
        assert (
            session.scalar(select(MemoryChunk).where(MemoryChunk.chat_group_id == room_id)) is None
        )
        assert (
            session.scalar(select(ActionDispatch).where(ActionDispatch.chat_group_id == room_id))
            is None
        )
        assert session.scalar(select(AuditRun).where(AuditRun.chat_group_id == room_id)) is None
        assert session.scalar(select(DurableJob).where(DurableJob.chat_group_id == room_id)) is None
        assert session.scalar(select(WakeupTask).where(WakeupTask.chat_group_id == room_id)) is None


def test_delete_chat_group_without_actions_cleans_failed_rounds(client, auth_headers):
    container = client.app.state.container
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={
            "name": "No Action Cleanup Group",
            "character_id": character_id,
            "selected_model_id": model_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    room_id = create_response.json()["id"]

    with container.session_factory() as session:
        session.add(
            FailedRound(
                chat_group_id=room_id, action_id=None, event_type="chat", reason="orphan cleanup"
            )
        )
        session.commit()

    delete_response = client.delete(f"/api/v1/chat-groups/{room_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text

    with container.session_factory() as session:
        assert (
            session.scalar(select(FailedRound).where(FailedRound.chat_group_id == room_id)) is None
        )
