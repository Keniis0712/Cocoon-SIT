def test_access_and_workspace_routes_return_typed_contracts(client, auth_headers, default_cocoon_id):
    logout = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "missing-token"},
    )
    assert logout.status_code == 200, logout.text
    assert logout.json() == {"message": "logged out"}

    bind = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/tags",
        headers=auth_headers,
        json={"tag_id": "focus"},
    )
    assert bind.status_code == 200, bind.text
    assert set(bind.json().keys()) == {"binding_id", "tag_id"}

    tags = client.get(f"/api/v1/cocoons/{default_cocoon_id}/tags", headers=auth_headers)
    assert tags.status_code == 200, tags.text
    assert {"id", "tag_id", "created_at"} <= set(tags.json()[0].keys())

    memory = client.get(f"/api/v1/memory/{default_cocoon_id}", headers=auth_headers)
    assert memory.status_code == 200, memory.text
    if memory.json():
        assert {"id", "scope", "summary", "content", "tags_json", "created_at"} <= set(memory.json()[0].keys())


def test_cocoon_state_route_returns_session_state(client, auth_headers, default_cocoon_id):
    response = client.get(f"/api/v1/cocoons/{default_cocoon_id}/state", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert {"id", "cocoon_id", "chat_group_id", "relation_score", "persona_json", "active_tags_json"} <= set(
        response.json().keys()
    )


def test_observability_routes_return_typed_contracts(client, worker_runtime, auth_headers, default_cocoon_id):
    send = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "contract audit message", "client_request_id": "contract-audit-1", "timezone": "UTC"},
    )
    assert send.status_code == 202, send.text
    assert worker_runtime.process_next_chat_dispatch() is True

    audits = client.get("/api/v1/audits", headers=auth_headers)
    assert audits.status_code == 200, audits.text
    run = audits.json()[0]
    assert {"id", "cocoon_id", "action_id", "operation_type", "status", "started_at", "finished_at"} <= set(run.keys())

    detail = client.get(f"/api/v1/audits/{run['id']}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert {"run", "steps", "artifacts", "links"} == set(payload.keys())
    assert {"id", "operation_type", "status"} <= set(payload["run"].keys())
    if payload["steps"]:
        assert {"id", "step_name", "status", "started_at", "finished_at", "meta_json"} <= set(payload["steps"][0].keys())
    if payload["artifacts"]:
        assert {"id", "kind", "storage_backend", "metadata_json", "created_at"} <= set(payload["artifacts"][0].keys())
    if payload["links"]:
        assert {"id", "relation", "created_at"} <= set(payload["links"][0].keys())

    artifacts = client.get("/api/v1/admin/artifacts", headers=auth_headers)
    assert artifacts.status_code == 200, artifacts.text
    if artifacts.json():
        assert {"id", "kind", "storage_backend", "metadata_json", "created_at"} <= set(artifacts.json()[0].keys())

    cleanup = client.post("/api/v1/admin/artifacts/cleanup", headers=auth_headers, json={})
    assert cleanup.status_code == 200, cleanup.text
    assert {"id", "job_type", "status", "payload_json"} <= set(cleanup.json().keys())


def test_job_enqueue_routes_return_typed_contracts(client, auth_headers, default_cocoon_id, create_branch_cocoon):
    source_cocoon_id = create_branch_cocoon("Contract Source")["id"]

    pull = client.post(
        "/api/v1/pulls",
        headers=auth_headers,
        json={"source_cocoon_id": source_cocoon_id, "target_cocoon_id": default_cocoon_id},
    )
    assert pull.status_code == 200, pull.text
    assert set(pull.json().keys()) == {"job_id", "pull_job_id", "status"}

    merge = client.post(
        "/api/v1/merges",
        headers=auth_headers,
        json={"source_cocoon_id": source_cocoon_id, "target_cocoon_id": default_cocoon_id},
    )
    assert merge.status_code == 200, merge.text
    assert set(merge.json().keys()) == {"job_id", "merge_job_id", "status"}


def test_manual_wakeup_api_is_not_exposed(client, auth_headers, default_cocoon_id):
    response = client.post(
        "/api/v1/wakeup",
        headers=auth_headers,
        json={"cocoon_id": default_cocoon_id, "reason": "manual wakeup"},
    )
    assert response.status_code == 404, response.text
