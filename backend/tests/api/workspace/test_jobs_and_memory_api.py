from sqlalchemy import select

from app.models import (
    Character,
    CharacterAcl,
    Cocoon,
    MemoryChunk,
    Message,
    Role,
    SessionState,
    User,
)
from app.services.security.encryption import hash_secret


def _login_headers(client, username: str, password: str = "secret") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_memory_routes_support_listing_compaction_and_delete(client, auth_headers, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        memory = MemoryChunk(
            cocoon_id=default_cocoon_id,
            scope="dialogue",
            summary="Remember this",
            content="Remember this memory",
        )
        session.add(memory)
        session.commit()
        memory_id = memory.id

    list_response = client.get(f"/api/v1/memory/{default_cocoon_id}", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    payload = list_response.json()
    assert {"items", "overview"} <= set(payload.keys())
    assert any(item["id"] == memory_id for item in payload["items"])

    compact_response = client.post(
        f"/api/v1/memory/{default_cocoon_id}/compact",
        headers=auth_headers,
        json={},
    )
    assert compact_response.status_code == 200, compact_response.text
    assert compact_response.json()["job_type"] == "compaction"

    delete_response = client.delete(f"/api/v1/memory/{default_cocoon_id}/{memory_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["id"] == memory_id

    missing_delete = client.delete(f"/api/v1/memory/{default_cocoon_id}/{memory_id}", headers=auth_headers)
    assert missing_delete.status_code == 404, missing_delete.text


def test_child_cocoon_memory_listing_includes_parent_chain_memories(client, auth_headers, create_branch_cocoon):
    container = client.app.state.container
    child_id = create_branch_cocoon("Memory Child")["id"]

    with container.session_factory() as session:
        child = session.get(Cocoon, child_id)
        assert child is not None
        assert child.parent_id is not None
        parent_memory = MemoryChunk(
            cocoon_id=child.parent_id,
            scope="dialogue",
            summary="Parent memory",
            content="Parent memory",
        )
        child_memory = MemoryChunk(
            cocoon_id=child_id,
            scope="dialogue",
            summary="Child memory",
            content="Child memory",
        )
        session.add_all([parent_memory, child_memory])
        session.commit()

    list_response = client.get(f"/api/v1/memory/{child_id}", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    summaries = [item["summary"] for item in list_response.json()["items"]]
    assert "Parent memory" in summaries
    assert "Child memory" in summaries


def test_checkpoint_and_rollback_routes_validate_anchor_and_enqueue_job(client, auth_headers, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        message = Message(cocoon_id=default_cocoon_id, role="user", content="Checkpoint anchor")
        session.add(message)
        session.commit()
        message_id = message.id

    missing_checkpoint = client.post(
        "/api/v1/checkpoints",
        headers=auth_headers,
        json={"cocoon_id": default_cocoon_id, "anchor_message_id": "missing", "label": "bad"},
    )
    assert missing_checkpoint.status_code == 404, missing_checkpoint.text

    create_checkpoint = client.post(
        "/api/v1/checkpoints",
        headers=auth_headers,
        json={"cocoon_id": default_cocoon_id, "anchor_message_id": message_id, "label": "before-change"},
    )
    assert create_checkpoint.status_code == 200, create_checkpoint.text
    checkpoint_id = create_checkpoint.json()["id"]

    list_response = client.get(f"/api/v1/checkpoints/{default_cocoon_id}", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == checkpoint_id for item in list_response.json())

    rollback_response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/rollback",
        headers=auth_headers,
        json={"checkpoint_id": checkpoint_id},
    )
    assert rollback_response.status_code == 200, rollback_response.text
    assert rollback_response.json()["job_type"] == "rollback"
    assert rollback_response.json()["payload_json"] == {"checkpoint_id": checkpoint_id}


def test_pull_and_merge_routes_filter_inaccessible_jobs(client, auth_headers):
    container = client.app.state.container

    with container.session_factory() as session:
        admin = session.scalar(select(User).where(User.username == "admin"))
        model_id = session.scalar(select(Cocoon.selected_model_id).limit(1))
        assert admin is not None
        assert model_id is not None

        role = Role(
            name="api-pull-merge-viewer",
            permissions_json={
                "cocoons:read": True,
                "pulls:write": True,
                "merges:write": True,
            },
        )
        session.add(role)
        session.flush()
        viewer = User(
            username="api-pull-merge-user",
            email="api-pull-merge-user@example.com",
            password_hash=hash_secret("secret"),
            role_id=role.id,
        )
        session.add(viewer)
        session.flush()

        visible_character = Character(
            name="Visible API Character",
            prompt_summary="visible",
            settings_json={},
            created_by_user_id=admin.id,
        )
        hidden_character = Character(
            name="Hidden API Character",
            prompt_summary="hidden",
            settings_json={},
            created_by_user_id=admin.id,
        )
        session.add_all([visible_character, hidden_character])
        session.flush()
        session.add(
            CharacterAcl(
                character_id=visible_character.id,
                subject_type="role",
                subject_id=role.id,
                can_read=True,
                can_use=True,
            )
        )

        visible_source = Cocoon(
            name="Visible Source",
            owner_user_id=admin.id,
            character_id=visible_character.id,
            selected_model_id=model_id,
        )
        visible_target = Cocoon(
            name="Visible Target",
            owner_user_id=admin.id,
            character_id=visible_character.id,
            selected_model_id=model_id,
        )
        hidden_source = Cocoon(
            name="Hidden Source",
            owner_user_id=admin.id,
            character_id=hidden_character.id,
            selected_model_id=model_id,
        )
        hidden_target = Cocoon(
            name="Hidden Target",
            owner_user_id=admin.id,
            character_id=hidden_character.id,
            selected_model_id=model_id,
        )
        session.add_all([visible_source, visible_target, hidden_source, hidden_target])
        session.flush()
        session.add_all(
            [
                SessionState(cocoon_id=visible_source.id, persona_json={}, active_tags_json=[]),
                SessionState(cocoon_id=visible_target.id, persona_json={}, active_tags_json=[]),
                SessionState(cocoon_id=hidden_source.id, persona_json={}, active_tags_json=[]),
                SessionState(cocoon_id=hidden_target.id, persona_json={}, active_tags_json=[]),
            ]
        )
        session.commit()

        visible_source_id = visible_source.id
        visible_target_id = visible_target.id
        hidden_source_id = hidden_source.id
        hidden_target_id = hidden_target.id

    viewer_headers = _login_headers(client, "api-pull-merge-user")

    visible_pull = client.post(
        "/api/v1/pulls",
        headers=auth_headers,
        json={"source_cocoon_id": visible_source_id, "target_cocoon_id": visible_target_id},
    )
    hidden_pull = client.post(
        "/api/v1/pulls",
        headers=auth_headers,
        json={"source_cocoon_id": hidden_source_id, "target_cocoon_id": hidden_target_id},
    )
    visible_merge = client.post(
        "/api/v1/merges",
        headers=auth_headers,
        json={"source_cocoon_id": visible_source_id, "target_cocoon_id": visible_target_id},
    )
    hidden_merge = client.post(
        "/api/v1/merges",
        headers=auth_headers,
        json={"source_cocoon_id": hidden_source_id, "target_cocoon_id": hidden_target_id},
    )
    assert visible_pull.status_code == 200, visible_pull.text
    assert hidden_pull.status_code == 200, hidden_pull.text
    assert visible_merge.status_code == 200, visible_merge.text
    assert hidden_merge.status_code == 200, hidden_merge.text

    pull_list = client.get("/api/v1/pulls", headers=viewer_headers)
    merge_list = client.get("/api/v1/merges", headers=viewer_headers)
    assert pull_list.status_code == 200, pull_list.text
    assert merge_list.status_code == 200, merge_list.text

    assert [(item["source_cocoon_id"], item["target_cocoon_id"]) for item in pull_list.json()] == [
        (visible_source_id, visible_target_id)
    ]
    assert [(item["source_cocoon_id"], item["target_cocoon_id"]) for item in merge_list.json()] == [
        (visible_source_id, visible_target_id)
    ]
