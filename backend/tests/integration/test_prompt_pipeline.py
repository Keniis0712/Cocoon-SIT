from datetime import UTC, datetime
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import ActionDispatch, AuditArtifact, AuditRun, AuditStep, Cocoon, CocoonTagBinding, MemoryChunk, SessionState, TagRegistry

pytestmark = pytest.mark.integration


def _read_artifact_payload(artifact: AuditArtifact) -> dict:
    assert artifact.storage_path is not None
    return json.loads(Path(artifact.storage_path).read_text(encoding="utf-8"))


def test_runtime_uses_meta_and_system_prompt_templates(
    client,
    auth_headers,
    worker_runtime,
    default_cocoon_id,
):
    system_update = client.put(
        "/api/v1/prompt-templates/system",
        headers=auth_headers,
        json={
            "name": "System Template",
            "description": "Include a system marker",
            "content": "SYSTEM CUSTOM MARKER\n{{ character_settings }}\n{{ session_state }}\n{{ provider_capabilities }}",
        },
    )
    assert system_update.status_code == 200, system_update.text
    meta_update = client.put(
        "/api/v1/prompt-templates/meta",
        headers=auth_headers,
        json={
            "name": "Meta Template",
            "description": "Include a meta marker",
            "content": (
                "META CUSTOM MARKER\n{{ character_settings }}\n{{ session_state }}\n"
                "{{ visible_messages }}\n{{ memory_context }}\n{{ runtime_event }}\n"
                "{{ wakeup_context }}\n{{ merge_context }}\n{{ provider_capabilities }}"
            ),
        },
    )
    assert meta_update.status_code == 200, meta_update.text

    send_response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "Show the runtime prompt snapshots",
            "client_request_id": "runtime-prompt-1",
            "timezone": "UTC",
        },
    )
    assert send_response.status_code == 202, send_response.text
    assert worker_runtime.process_next_chat_dispatch() is True

    with client.app.state.container.session_factory() as session:
        action = session.scalar(
            select(ActionDispatch).where(ActionDispatch.client_request_id == "runtime-prompt-1")
        )
        assert action is not None
        run = session.scalar(select(AuditRun).where(AuditRun.action_id == action.id))
        assert run is not None
        meta_step = session.scalar(
            select(AuditStep).where(AuditStep.run_id == run.id, AuditStep.step_name == "meta_node")
        )
        generator_step = session.scalar(
            select(AuditStep).where(AuditStep.run_id == run.id, AuditStep.step_name == "generator_node")
        )
        assert meta_step is not None
        assert generator_step is not None

        meta_snapshot = session.scalar(
            select(AuditArtifact).where(
                AuditArtifact.step_id == meta_step.id,
                AuditArtifact.kind == "prompt_snapshot",
                AuditArtifact.summary == "meta prompt snapshot",
            )
        )
        system_snapshot = session.scalar(
            select(AuditArtifact).where(
                AuditArtifact.step_id == generator_step.id,
                AuditArtifact.kind == "prompt_snapshot",
                AuditArtifact.summary == "system prompt snapshot",
            )
        )
        generator_snapshot = session.scalar(
            select(AuditArtifact).where(
                AuditArtifact.step_id == generator_step.id,
                AuditArtifact.kind == "prompt_snapshot",
                AuditArtifact.summary == "generator prompt snapshot",
            )
        )
        assert meta_snapshot is not None
        assert system_snapshot is not None
        assert generator_snapshot is not None

        meta_rendered = _read_artifact_payload(meta_snapshot)["rendered_prompt"]
        assert "META CUSTOM MARKER" in meta_rendered
        assert "raw_payload" not in meta_rendered
        assert "SYSTEM CUSTOM MARKER" in _read_artifact_payload(system_snapshot)["rendered_prompt"]
        assert _read_artifact_payload(generator_snapshot)["template_type"] == "generator"


def test_wakeup_context_is_available_to_meta_templates(
    client,
    auth_headers,
    worker_runtime,
    default_cocoon_id,
):
    response = client.put(
        "/api/v1/prompt-templates/meta",
        headers=auth_headers,
        json={
            "name": "Meta Template",
            "description": "Wakeup-aware meta template",
            "content": (
                "Wakeup-aware meta\n{{ character_settings }}\n{{ session_state }}\n"
                "{{ visible_messages }}\n{{ memory_context }}\n{{ runtime_event }}\n"
                "{{ wakeup_context }}\n{{ merge_context }}\n{{ provider_capabilities }}"
            ),
        },
    )
    assert response.status_code == 200, response.text

    container = client.app.state.container
    with container.session_factory() as session:
        container.scheduler_node.schedule_wakeup(
            session,
            cocoon_id=default_cocoon_id,
            run_at=datetime.now(UTC),
            reason="scheduled from prompt test",
            payload_json={"scheduled_by": "test"},
        )
        session.commit()
    assert worker_runtime.process_next_durable_job() is True

    with client.app.state.container.session_factory() as session:
        run = session.scalars(
            select(AuditRun)
            .where(AuditRun.operation_type == "wakeup")
            .order_by(AuditRun.started_at.desc())
        ).first()
        assert run is not None
        meta_step = session.scalar(
            select(AuditStep).where(AuditStep.run_id == run.id, AuditStep.step_name == "meta_node")
        )
        assert meta_step is not None
        meta_variables = session.scalar(
            select(AuditArtifact).where(
                AuditArtifact.step_id == meta_step.id,
                AuditArtifact.kind == "prompt_variables",
                AuditArtifact.summary == "meta prompt variables snapshot",
            )
        )
        assert meta_variables is not None
        payload = _read_artifact_payload(meta_variables)
        assert payload["variables"]["wakeup_context"]["reason"] == "scheduled from prompt test"
        assert "provider_capabilities" in payload["variables"]


def test_memory_summary_template_drives_compaction(
    client,
    auth_headers,
    worker_runtime,
    default_cocoon_id,
):
    response = client.put(
        "/api/v1/prompt-templates/memory_summary",
        headers=auth_headers,
        json={
            "name": "Memory Summary Template",
            "description": "Custom compaction prompt",
            "content": "MEMORY SUMMARY CUSTOM MARKER\n{{ visible_messages }}\n{{ memory_context }}",
        },
    )
    assert response.status_code == 200, response.text

    send_response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "Create enough history to compact",
            "client_request_id": "compact-prompt-1",
            "timezone": "UTC",
        },
    )
    assert send_response.status_code == 202, send_response.text
    assert worker_runtime.process_next_chat_dispatch() is True

    compact_response = client.post(
        f"/api/v1/memory/{default_cocoon_id}/compact",
        headers=auth_headers,
        json={},
    )
    assert compact_response.status_code == 200, compact_response.text
    assert worker_runtime.process_next_durable_job() is True

    with client.app.state.container.session_factory() as session:
        run = session.scalars(
            select(AuditRun)
            .where(AuditRun.operation_type == "compaction")
            .order_by(AuditRun.started_at.desc())
        ).first()
        assert run is not None
        step = session.scalar(select(AuditStep).where(AuditStep.run_id == run.id, AuditStep.step_name == "compaction"))
        assert step is not None
        prompt_snapshot = session.scalar(
            select(AuditArtifact).where(
                AuditArtifact.step_id == step.id,
                AuditArtifact.kind == "prompt_snapshot",
                AuditArtifact.summary == "memory_summary prompt snapshot",
            )
        )
        assert prompt_snapshot is not None
        assert "MEMORY SUMMARY CUSTOM MARKER" in _read_artifact_payload(prompt_snapshot)["rendered_prompt"]
        chunks = list(
            session.scalars(select(MemoryChunk).where(MemoryChunk.cocoon_id == default_cocoon_id)).all()
        )
        assert any((chunk.meta_json or {}).get("source_kind") == "compaction" for chunk in chunks)


def test_runtime_prompt_exposes_readable_tag_metadata_when_state_is_stale(
    client,
    auth_headers,
    worker_runtime,
    default_cocoon_id,
):
    with client.app.state.container.session_factory() as session:
        cocoon = session.get(Cocoon, default_cocoon_id)
        assert cocoon is not None
        default_tag = session.scalar(
            select(TagRegistry).where(
                TagRegistry.owner_user_id == cocoon.owner_user_id,
                TagRegistry.is_system.is_(True),
            )
        )
        assert default_tag is not None
        owner_user_id = default_tag.owner_user_id
        focus_tag = TagRegistry(
            owner_user_id=owner_user_id,
            tag_id="focus-readable",
            brief="Readable focus tag",
            visibility="private",
            is_isolated=True,
            meta_json={},
        )
        session.add(focus_tag)
        session.flush()
        session.add(CocoonTagBinding(cocoon_id=default_cocoon_id, tag_id=focus_tag.id))
        state = session.scalar(select(SessionState).where(SessionState.cocoon_id == default_cocoon_id))
        assert state is not None
        state.active_tags_json = [default_tag.id]
        session.commit()

    response = client.put(
        "/api/v1/prompt-templates/meta",
        headers=auth_headers,
        json={
            "name": "Meta Template",
            "description": "Readable tag metadata",
            "content": (
                "Readable tags meta\n{{ session_state }}\n{{ visible_messages }}\n"
                "{{ memory_context }}\n{{ merge_context }}"
            ),
        },
    )
    assert response.status_code == 200, response.text

    send_response = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/messages",
        headers=auth_headers,
        json={
            "content": "Check readable tag metadata",
            "client_request_id": "runtime-tags-1",
            "timezone": "UTC",
        },
    )
    assert send_response.status_code == 202, send_response.text
    assert worker_runtime.process_next_chat_dispatch() is True

    with client.app.state.container.session_factory() as session:
        action = session.scalar(
            select(ActionDispatch).where(ActionDispatch.client_request_id == "runtime-tags-1")
        )
        assert action is not None
        run = session.scalar(select(AuditRun).where(AuditRun.action_id == action.id))
        assert run is not None
        meta_step = session.scalar(
            select(AuditStep).where(AuditStep.run_id == run.id, AuditStep.step_name == "meta_node")
        )
        assert meta_step is not None
        meta_variables = session.scalar(
            select(AuditArtifact).where(
                AuditArtifact.step_id == meta_step.id,
                AuditArtifact.kind == "prompt_variables",
                AuditArtifact.summary == "meta prompt variables snapshot",
            )
        )
        assert meta_variables is not None

        payload = _read_artifact_payload(meta_variables)["variables"]
        active_tags = payload["session_state"]["active_tags"]
        assert active_tags
        assert active_tags[0] == "default"
        assert "focus-readable" in active_tags
        assert payload["tag_catalog"]
        tag_catalog_ids = [item["tag_id"] for item in payload["tag_catalog"]]
        assert tag_catalog_ids[0] == "default"
        assert "focus-readable" in tag_catalog_ids

        visible_message = payload["visible_messages"][0]
        assert "tag_refs" not in visible_message
        assert "tag_visibility" not in visible_message
        if visible_message["tags"]:
            assert visible_message["tags"][0] == "default"
