from datetime import UTC, datetime

from sqlalchemy import select

from app.models import (
    ActionDispatch,
    AuditArtifact,
    AuditLink,
    AuditRun,
    AuditStep,
    Checkpoint,
    Cocoon,
    CocoonMergeJob,
    CocoonPullJob,
    DurableJob,
    FailedRound,
    MemoryChunk,
    Message,
    SessionState,
    WakeupTask,
)
from app.api.routes.workspace.cocoons import _delete_cocoon_subtree


def _default_character_and_model_ids(client, auth_headers):
    characters = client.get("/api/v1/characters", headers=auth_headers).json()
    models = client.get("/api/v1/providers/models", headers=auth_headers).json()
    return characters[0]["id"], models[0]["id"]


def test_cocoon_routes_support_create_update_tree_and_state(client, auth_headers, default_cocoon_id):
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_response = client.post(
        "/api/v1/cocoons",
        headers=auth_headers,
        json={
            "name": "API Child Cocoon",
            "character_id": character_id,
            "selected_model_id": model_id,
            "parent_id": default_cocoon_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    cocoon_id = create_response.json()["id"]

    list_response = client.get("/api/v1/cocoons", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == cocoon_id for item in list_response.json())

    update_response = client.patch(
        f"/api/v1/cocoons/{cocoon_id}",
        headers=auth_headers,
        json={
            "name": "API Child Cocoon Updated",
            "max_context_messages": 21,
            "auto_compaction_enabled": False,
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["name"] == "API Child Cocoon Updated"
    assert update_response.json()["max_context_messages"] == 21
    assert update_response.json()["auto_compaction_enabled"] is False

    get_response = client.get(f"/api/v1/cocoons/{cocoon_id}", headers=auth_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["id"] == cocoon_id

    tree_response = client.get("/api/v1/cocoons/tree", headers=auth_headers)
    assert tree_response.status_code == 200, tree_response.text
    parent = next(item for item in tree_response.json() if item["id"] == default_cocoon_id)
    assert any(child["id"] == cocoon_id for child in parent["children"])

    state_response = client.get(f"/api/v1/cocoons/{cocoon_id}/state", headers=auth_headers)
    assert state_response.status_code == 200, state_response.text
    assert state_response.json()["cocoon_id"] == cocoon_id


def test_cocoon_create_rejects_duplicate_root_and_state_returns_404_when_missing(
    client,
    auth_headers,
    default_cocoon_id,
):
    with client.app.state.container.session_factory() as session:
        root = session.get(Cocoon, default_cocoon_id)
        assert root is not None
        character_id = root.character_id
        model_id = root.selected_model_id
        state = session.get(SessionState, default_cocoon_id)
        assert state is not None
        session.delete(state)
        session.commit()

    duplicate_root = client.post(
        "/api/v1/cocoons",
        headers=auth_headers,
        json={
            "name": "Duplicate Root",
            "character_id": character_id,
            "selected_model_id": model_id,
        },
    )
    assert duplicate_root.status_code == 400, duplicate_root.text
    assert duplicate_root.json()["detail"] == "A root cocoon already exists for this user and character"

    state_response = client.get(f"/api/v1/cocoons/{default_cocoon_id}/state", headers=auth_headers)
    assert state_response.status_code == 404, state_response.text
    assert state_response.json()["detail"] == "Session state not found"


def test_delete_cocoon_cleans_subtree_and_related_records(
    client,
    auth_headers,
    create_branch_cocoon,
):
    container = client.app.state.container
    child_id = create_branch_cocoon("Delete Branch")["id"]

    with container.session_factory() as session:
        child = session.get(Cocoon, child_id)
        assert child is not None
        grandchild = Cocoon(
            name="Delete Grandchild",
            owner_user_id=child.owner_user_id,
            character_id=child.character_id,
            selected_model_id=child.selected_model_id,
            parent_id=child.id,
        )
        session.add(grandchild)
        session.flush()
        session.add(SessionState(cocoon_id=grandchild.id, persona_json={}, active_tags_json=[]))

        action = ActionDispatch(cocoon_id=child.id, event_type="chat", status="completed", payload_json={})
        session.add(action)
        session.flush()

        message = Message(cocoon_id=child.id, action_id=action.id, role="assistant", content="Delete me")
        session.add(message)
        session.flush()

        memory = MemoryChunk(
            cocoon_id=child.id,
            source_message_id=message.id,
            scope="dialogue",
            content="Delete this memory too",
        )
        session.add(memory)
        session.flush()

        session.add(Checkpoint(cocoon_id=child.id, anchor_message_id=message.id, label="before-delete"))
        job = DurableJob(cocoon_id=child.id, job_type="merge", lock_key="delete-branch", payload_json={})
        session.add(job)
        session.flush()
        session.add(
            WakeupTask(
                cocoon_id=child.id,
                run_at=datetime.now(UTC).replace(tzinfo=None),
                reason="delete wakeup",
                payload_json={},
            )
        )
        session.add(
            CocoonPullJob(
                durable_job_id=job.id,
                source_cocoon_id=child.id,
                target_cocoon_id=grandchild.id,
            )
        )
        session.add(
            CocoonMergeJob(
                durable_job_id=job.id,
                source_cocoon_id=child.id,
                target_cocoon_id=grandchild.id,
            )
        )

        run = AuditRun(cocoon_id=child.id, action_id=action.id, operation_type="chat")
        session.add(run)
        session.flush()
        step = AuditStep(run_id=run.id, step_name="generator")
        session.add(step)
        session.flush()
        artifact = AuditArtifact(run_id=run.id, step_id=step.id, kind="generator_output", metadata_json={})
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
        session.add(FailedRound(cocoon_id=child.id, action_id=action.id, event_type="chat", reason="delete"))
        grandchild_id = grandchild.id
        session.commit()

    delete_response = client.delete(f"/api/v1/cocoons/{child_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["id"] == child_id

    with container.session_factory() as session:
        assert session.get(Cocoon, child_id) is None
        assert session.get(Cocoon, grandchild_id) is None
        assert session.scalar(select(Message).where(Message.cocoon_id == child_id)) is None
        assert session.scalar(select(MemoryChunk).where(MemoryChunk.cocoon_id == child_id)) is None
        assert session.scalar(select(ActionDispatch).where(ActionDispatch.cocoon_id == child_id)) is None
        assert session.scalar(select(AuditRun).where(AuditRun.cocoon_id == child_id)) is None
        assert session.scalar(select(DurableJob).where(DurableJob.cocoon_id == child_id)) is None
        assert session.scalar(select(WakeupTask).where(WakeupTask.cocoon_id == child_id)) is None


def test_cocoon_update_selected_model_and_delete_without_actions(client, auth_headers, default_cocoon_id):
    character_id, model_id = _default_character_and_model_ids(client, auth_headers)

    create_response = client.post(
        "/api/v1/cocoons",
        headers=auth_headers,
        json={
            "name": "Leaf Cocoon",
            "character_id": character_id,
            "selected_model_id": model_id,
            "parent_id": default_cocoon_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    cocoon_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/cocoons/{cocoon_id}",
        headers=auth_headers,
        json={"selected_model_id": model_id},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["selected_model_id"] == model_id

    delete_response = client.delete(f"/api/v1/cocoons/{cocoon_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["id"] == cocoon_id

    with client.app.state.container.session_factory() as session:
        assert session.get(Cocoon, cocoon_id) is None
        assert session.scalar(select(FailedRound).where(FailedRound.cocoon_id == cocoon_id)) is None


def test_delete_cocoon_subtree_helper_is_noop_for_empty_ids(client):
    with client.app.state.container.session_factory() as session:
        _delete_cocoon_subtree(session, [])
