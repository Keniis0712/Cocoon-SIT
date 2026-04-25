from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import (
    ActionDispatch,
    AuditArtifact,
    Cocoon,
    DurableJob,
    MemoryChunk,
    SessionState,
    WakeupTask,
)


def _default_character_and_model_ids(client, auth_headers):
    characters = client.get("/api/v1/characters", headers=auth_headers).json()
    models = client.get("/api/v1/providers/models", headers=auth_headers).json()
    return characters[0]["id"], models[0]["id"]


def _process_all_chat_jobs(worker_runtime):
    while worker_runtime.process_next_chat_dispatch():
        pass


def _process_one_durable_job(worker_runtime):
    return worker_runtime.process_next_durable_job()


def _process_until_durable_job_completed(worker_runtime, client, job_id: str, max_attempts: int = 10) -> None:
    container = client.app.state.container
    for _ in range(max_attempts):
        with container.session_factory() as session:
            job = session.get(DurableJob, job_id)
            if job is not None and job.status == "completed":
                return
        if not worker_runtime.process_next_durable_job():
            break
    with container.session_factory() as session:
        job = session.get(DurableJob, job_id)
        assert job is not None
        assert job.status == "completed"


def test_resource_crud_and_tag_binding_flow(client, auth_headers):
    role = client.post(
        "/api/v1/roles",
        headers=auth_headers,
        json={"name": "qa", "permissions_json": {"cocoons:read": True}},
    )
    assert role.status_code == 200, role.text

    user = client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "username": "qa-user",
            "email": "qa@example.com",
            "password": "secret1",
            "role_id": role.json()["id"],
            "is_active": True,
        },
    )
    assert user.status_code == 200, user.text

    invite = client.post(
        "/api/v1/invites",
        headers=auth_headers,
        json={"prefix": "invite", "quota_total": 2},
    )
    assert invite.status_code == 200, invite.text
    invite_code = invite.json()["code"]

    redeem = client.post(
        f"/api/v1/invites/{invite_code}/redeem",
        headers=auth_headers,
        json={"user_id": user.json()["id"], "quota": 1},
    )
    assert redeem.status_code == 200, redeem.text

    group = client.post("/api/v1/groups", headers=auth_headers, json={"name": "ops"})
    assert group.status_code == 200, group.text
    member = client.post(
        f"/api/v1/groups/{group.json()['id']}/members",
        headers=auth_headers,
        json={"user_id": user.json()["id"], "member_role": "member"},
    )
    assert member.status_code == 200, member.text
    grant = client.post(
        "/api/v1/invites/grants",
        headers=auth_headers,
        json={"target_type": "GROUP", "target_id": group.json()["id"], "amount": 2, "is_unlimited": False},
    )
    assert grant.status_code == 200, grant.text
    group_summary = client.get(f"/api/v1/invites/summary/groups/{group.json()['id']}", headers=auth_headers)
    assert group_summary.status_code == 200, group_summary.text
    assert group_summary.json()["invite_quota_remaining"] == 2
    scoped_invite = client.post(
        "/api/v1/invites",
        headers=auth_headers,
        json={
            "prefix": "group",
            "quota_total": 1,
            "source_type": "GROUP",
            "source_id": group.json()["id"],
            "created_for_user_id": user.json()["id"],
        },
    )
    assert scoped_invite.status_code == 200, scoped_invite.text
    scoped_invite_code = scoped_invite.json()["code"]
    revoked = client.delete(f"/api/v1/invites/{scoped_invite_code}", headers=auth_headers)
    assert revoked.status_code == 200, revoked.text
    grants = client.get("/api/v1/invites/grants", headers=auth_headers)
    assert grants.status_code == 200, grants.text
    assert grants.json()

    character = client.post(
        "/api/v1/characters",
        headers=auth_headers,
        json={
            "name": "Ops Assistant",
            "prompt_summary": "Helps operate the platform",
            "settings_json": {"tone": "precise"},
        },
    )
    assert character.status_code == 200, character.text
    acl = client.post(
        f"/api/v1/characters/{character.json()['id']}/acl",
        headers=auth_headers,
        json={
            "subject_type": "role",
            "subject_id": role.json()["id"],
            "can_read": True,
            "can_use": True,
        },
    )
    assert acl.status_code == 200, acl.text

    provider = client.post(
        "/api/v1/providers",
        headers=auth_headers,
        json={
            "name": "mock-extra",
            "kind": "mock",
            "base_url": None,
            "capabilities_json": {"streaming": True},
        },
    )
    assert provider.status_code == 200, provider.text
    model = client.post(
        "/api/v1/providers/models",
        headers=auth_headers,
        json={
            "provider_id": provider.json()["id"],
            "model_name": "mock-extra-model",
            "model_kind": "chat",
            "is_default": False,
            "config_json": {"reply_prefix": "Mocked"},
        },
    )
    assert model.status_code == 200, model.text
    embedding_provider = client.post(
        "/api/v1/providers/embedding-providers",
        headers=auth_headers,
        json={
            "name": "embed-extra",
            "provider_id": provider.json()["id"],
            "model_name": "embed-model",
            "config_json": {"dims": 8},
            "is_enabled": True,
        },
    )
    assert embedding_provider.status_code == 200, embedding_provider.text

    tag = client.post(
        "/api/v1/tags",
        headers=auth_headers,
        json={"tag_id": "ops", "brief": "Operations", "visibility": "private", "is_isolated": False, "meta_json": {"color": "blue"}},
    )
    assert tag.status_code == 200, tag.text
    tag_id = tag.json()["id"]

    cocoon_ids = client.get("/api/v1/cocoons", headers=auth_headers).json()
    cocoon_id = cocoon_ids[0]["id"]
    bind = client.post(
        f"/api/v1/cocoons/{cocoon_id}/tags",
        headers=auth_headers,
        json={"tag_id": tag_id},
    )
    assert bind.status_code == 200, bind.text

    tree = client.get("/api/v1/cocoons/tree", headers=auth_headers)
    assert tree.status_code == 200, tree.text
    assert tree.json()


def test_wakeup_pull_merge_rollback_compaction_and_insights(
    client,
    worker_runtime,
    auth_headers,
    default_cocoon_id,
    create_branch_cocoon,
):
    source_cocoon_id = create_branch_cocoon("Source Branch")["id"]

    send_source = client.post(
        f"/api/v1/cocoons/{source_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "Knowledge from source", "client_request_id": "source-1", "timezone": "UTC"},
    )
    assert send_source.status_code == 202, send_source.text
    _process_all_chat_jobs(worker_runtime)

    container = client.app.state.container
    with container.session_factory() as session:
        container.scheduler_node.schedule_wakeup(
            session,
            cocoon_id=default_cocoon_id,
            run_at=datetime.now(UTC),
            reason="check in later",
            payload_json={"scheduled_by": "test"},
        )
        session.commit()
    assert _process_one_durable_job(worker_runtime) is True

    pull = client.post(
        "/api/v1/pulls",
        headers=auth_headers,
        json={"source_cocoon_id": source_cocoon_id, "target_cocoon_id": default_cocoon_id},
    )
    assert pull.status_code == 200, pull.text
    assert _process_one_durable_job(worker_runtime) is True

    merge = client.post(
        "/api/v1/merges",
        headers=auth_headers,
        json={"source_cocoon_id": source_cocoon_id, "target_cocoon_id": default_cocoon_id},
    )
    assert merge.status_code == 200, merge.text
    assert _process_one_durable_job(worker_runtime) is True

    default_messages = client.get(f"/api/v1/cocoons/{default_cocoon_id}/messages", headers=auth_headers)
    assert default_messages.status_code == 200, default_messages.text
    roles = [item["role"] for item in default_messages.json()]
    assert "assistant" in roles or "system" in roles

    first_round = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "Round before checkpoint", "client_request_id": "rollback-1", "timezone": "UTC"},
    )
    assert first_round.status_code == 202, first_round.text
    _process_all_chat_jobs(worker_runtime)
    messages_after_first = client.get(f"/api/v1/cocoons/{default_cocoon_id}/messages", headers=auth_headers).json()
    checkpoint = client.post(
        "/api/v1/checkpoints",
        headers=auth_headers,
        json={
            "cocoon_id": default_cocoon_id,
            "anchor_message_id": messages_after_first[-1]["id"],
            "label": "before-second-round",
        },
    )
    assert checkpoint.status_code == 200, checkpoint.text

    second_round = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={"content": "Round after checkpoint", "client_request_id": "rollback-2", "timezone": "UTC"},
    )
    assert second_round.status_code == 202, second_round.text
    _process_all_chat_jobs(worker_runtime)
    before_rollback_count = len(
        client.get(f"/api/v1/cocoons/{default_cocoon_id}/messages", headers=auth_headers).json()
    )

    rollback = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/rollback",
        headers=auth_headers,
        json={"checkpoint_id": checkpoint.json()["id"]},
    )
    assert rollback.status_code == 200, rollback.text
    _process_until_durable_job_completed(worker_runtime, client, rollback.json()["id"])

    after_rollback_messages = client.get(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
    ).json()
    assert len(after_rollback_messages) < before_rollback_count

    compact = client.post(
        f"/api/v1/memory/{default_cocoon_id}/compact",
        headers=auth_headers,
        json={},
    )
    assert compact.status_code == 200, compact.text
    assert _process_one_durable_job(worker_runtime) is True

    insights = client.get("/api/v1/insights/summary", headers=auth_headers)
    assert insights.status_code == 200, insights.text
    names = {item["name"] for item in insights.json()["metrics"]}
    assert {"users", "messages", "memory_chunks", "audit_runs"} <= names

    audits = client.get("/api/v1/audits", headers=auth_headers)
    assert audits.status_code == 200, audits.text
    assert audits.json()

    artifacts = client.get("/api/v1/admin/artifacts", headers=auth_headers)
    assert artifacts.status_code == 200, artifacts.text
    artifact_id = artifacts.json()[0]["id"]
    cleanup = client.post(
        "/api/v1/admin/artifacts/cleanup/manual",
        headers=auth_headers,
        json={"artifact_ids": [artifact_id]},
    )
    assert cleanup.status_code == 200, cleanup.text
    _process_until_durable_job_completed(worker_runtime, client, cleanup.json()["id"])

    with client.app.state.container.session_factory() as session:
        manual_wakeup_task = session.scalar(
            select(WakeupTask)
            .where(
                WakeupTask.cocoon_id == default_cocoon_id,
                WakeupTask.reason == "check in later",
            )
            .order_by(WakeupTask.created_at.asc())
        )
        assert manual_wakeup_task is not None
        assert manual_wakeup_task.status == "completed"

        queued_idle_wakeups = list(
            session.scalars(
                select(WakeupTask).where(
                    WakeupTask.cocoon_id == default_cocoon_id,
                    WakeupTask.status == "queued",
                )
            ).all()
        )
        assert all(task.payload_json.get("trigger_kind") == "idle_timeout" for task in queued_idle_wakeups)

        default_cocoon = session.get(Cocoon, default_cocoon_id)
        assert default_cocoon is not None
        assert default_cocoon.rollback_anchor_msg_id == checkpoint.json()["anchor_message_id"]

        compaction_chunks = [
            chunk
            for chunk in session.scalars(
                select(MemoryChunk).where(MemoryChunk.cocoon_id == default_cocoon_id)
            ).all()
            if (chunk.meta_json or {}).get("source_kind") == "compaction"
        ]
        assert compaction_chunks

        deleted_artifact = session.get(AuditArtifact, artifact_id)
        assert deleted_artifact is not None
        assert deleted_artifact.deleted_at is not None

        completed_actions = list(
            session.scalars(
                select(ActionDispatch).where(ActionDispatch.status == "completed")
            ).all()
        )
        assert completed_actions

        durable_jobs = list(session.scalars(select(DurableJob)).all())
        assert durable_jobs
        assert any(job.status == "completed" for job in durable_jobs)
