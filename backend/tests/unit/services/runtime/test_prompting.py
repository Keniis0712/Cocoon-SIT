from types import SimpleNamespace

from app.services.runtime.prompting import (
    _mentionable_for_target,
    _pending_wakeup_payload,
    _resolve_tag_name,
    _runtime_memory_payload,
    _runtime_message_payload,
    _serialize_tag,
    _serialize_tags,
    _tag_catalog,
    _visibility_description,
    build_runtime_prompt_variables,
    record_prompt_render_artifacts,
)
from app.services.runtime.types import ContextPackage, RuntimeEvent


def _build_context(*, target_type: str = "chat_group") -> ContextPackage:
    runtime_event = RuntimeEvent(
        event_type="chat",
        cocoon_id="cocoon-1" if target_type == "cocoon" else None,
        chat_group_id="group-1" if target_type == "chat_group" else None,
        action_id="action-1",
        payload={
            "source": "user",
            "message_id": "3d12bf20-37c7-43c7-85b6-941ad74eb22f",
            "client_request_id": "2ac72c91-27db-4cfd-b3f7-04ca0f4f8950",
            "timezone": "Asia/Shanghai",
        },
    )
    return ContextPackage(
        runtime_event=runtime_event,
        conversation=SimpleNamespace(name="Demo Cocoon"),
        character=SimpleNamespace(
            settings_json={"voice": "warm"},
            prompt_summary="friendly companion",
        ),
        session_state=SimpleNamespace(
            relation_score=3,
            persona_json={"mood": "curious"},
            active_tags_json=["tag-public", "tag-group"],
        ),
        visible_messages=[],
        memory_context=[],
        external_context={
            "pending_wakeups": [{"id": "wake-1"}],
            "wakeup_context": {"reason": "idle timeout"},
            "merge_context": {
                "source_state": {
                    "relation_score": 2,
                    "persona_json": {"tone": "calm"},
                    "active_tags_json": ["tag-public"],
                }
            },
            "tag_catalog_by_ref": {
                "tag-public": {
                    "brief": "safe tag",
                    "visibility": "public",
                    "meta_json": {"display_name": "Public Tag"},
                },
                "tag-group": {
                    "brief": "group only",
                    "visibility": "group_private",
                    "tag_id": "group-id",
                },
                "tag-private": {
                    "brief": "private tag",
                    "visibility": "private",
                    "is_isolated": True,
                },
            },
        },
    )


def test_prompting_helpers_handle_tag_lookup_and_visibility():
    context = _build_context()
    catalog = _tag_catalog(context)

    assert _resolve_tag_name({"meta_json": {"name": "Alpha"}}, "fallback") == "Alpha"
    assert _resolve_tag_name({"tag_id": "tag-1"}, "fallback") == "tag-1"
    assert _resolve_tag_name({}, "fallback") == "fallback"
    assert _visibility_description("public").startswith("Visible across")
    assert "custom" in _visibility_description("custom_scope")
    assert _mentionable_for_target(["tag-public"], context, catalog) is True
    assert _mentionable_for_target(["tag-group"], context, catalog) is False


def test_prompting_serializes_tags_messages_and_memory():
    context = _build_context(target_type="cocoon")
    catalog = _tag_catalog(context)
    message = SimpleNamespace(
        role="user",
        content="Hello there",
        sender_user_id="user-1",
        is_retracted=True,
        tags_json=["tag-public", "tag-group"],
    )
    memory = SimpleNamespace(
        scope="dialogue",
        summary="User preference",
        content="Likes tea",
        owner_user_id="user-1",
        character_id="char-1",
        tags_json=["tag-private"],
        chat_group_id=None,
        cocoon_id="cocoon-1",
    )

    serialized_tag = _serialize_tag("tag-public", context, catalog)
    serialized_tags = _serialize_tags(["tag-public", "tag-group"], context, catalog)
    message_payload = _runtime_message_payload(message, context, catalog)
    memory_payload = _runtime_memory_payload(memory, context, catalog)

    assert serialized_tag["name"] == "Public Tag"
    assert serialized_tag["mentionable_in_current_target"] is True
    assert serialized_tags[1]["name"] == "group-id"
    assert "[system note: this message was later retracted]" in message_payload["content"]
    assert message_payload["speaker"] == "you"
    assert "sender_user_id" not in message_payload
    assert message_payload["mentionable_in_current_target"] is True
    assert memory_payload["source"] == "cocoon"
    assert memory_payload["mentionable_in_current_target"] is False
    assert memory_payload["tags"][0]["is_isolated"] is True
    assert "owner_user_id" not in memory_payload


def test_build_runtime_prompt_variables_builds_full_payload():
    context = _build_context(target_type="cocoon")
    context.visible_messages = [
        SimpleNamespace(
            role="user",
            content="Hi",
            sender_user_id="user-1",
            is_retracted=False,
            tags_json=["tag-public"],
        )
    ]
    context.memory_context = [
        SimpleNamespace(
            scope="dialogue",
            summary="Pref",
            content="Likes tea",
            owner_user_id="user-1",
            character_id="char-1",
            tags_json=["tag-public"],
            chat_group_id="group-1",
            cocoon_id=None,
        )
    ]

    payload = build_runtime_prompt_variables(
        context,
        provider_capabilities={
            "streaming": True,
            "provider_kind": "mock",
            "model_name": "gpt-test",
        },
    )

    assert payload["character_settings"]["prompt_summary"] == "friendly companion"
    assert payload["conversation_target"] == {"type": "cocoon", "name": "Demo Cocoon"}
    assert payload["visible_messages"][0]["tags"][0]["name"] == "Public Tag"
    assert payload["visible_messages"][0]["speaker"] == "you"
    assert payload["memory_context"][0]["source"] == "chat_group"
    assert payload["runtime_event"]["source"] == "user"
    assert payload["runtime_event"]["timezone"] == "Asia/Shanghai"
    assert "message_id" not in payload["runtime_event"]
    assert payload["pending_wakeups"] == [{"run_at": None, "reason": None, "status": None, "has_payload": False}]
    assert payload["merge_context"]["source_state"]["active_tags"][0]["name"] == "Public Tag"
    assert payload["provider_capabilities"] == {"streaming": True}


def test_build_runtime_prompt_variables_drops_duplicate_prompt_summary():
    context = _build_context(target_type="cocoon")
    context.character.settings_json = {
        "personality_prompt": "same role prompt",
        "prompt_summary": "same role prompt",
    }
    context.character.prompt_summary = "same role prompt"

    payload = build_runtime_prompt_variables(context)

    assert payload["character_settings"] == {"personality_prompt": "same role prompt"}


def test_build_runtime_prompt_variables_handles_non_dict_catalog_and_merge_payload():
    context = _build_context()
    context.external_context["tag_catalog_by_ref"] = []
    context.external_context["merge_context"] = "plain"

    payload = build_runtime_prompt_variables(context)

    assert payload["session_state"]["active_tags"][0]["name"] == "tag-public"
    assert payload["merge_context"] == "plain"


def test_pending_wakeup_payload_hides_ids_and_payload_details():
    payload = _pending_wakeup_payload(
        [
            {
                "id": "wake-1",
                "run_at": "2026-04-22T12:00:00",
                "reason": "follow up",
                "status": "queued",
                "payload_json": {"source_cocoon_id": "abc"},
            }
        ]
    )

    assert payload == [
        {
            "run_at": "2026-04-22T12:00:00",
            "reason": "follow up",
            "status": "queued",
            "has_payload": True,
        }
    ]


def test_record_prompt_render_artifacts_links_variable_and_snapshot_artifacts():
    recorded_json = []
    recorded_links = []

    class _AuditService:
        def record_json_artifact(self, *args, **kwargs):
            recorded_json.append((args, kwargs))
            suffix = "variables" if len(recorded_json) == 1 else "snapshot"
            return SimpleNamespace(id=f"artifact-{suffix}")

        def record_link(self, *args, **kwargs):
            recorded_links.append((args, kwargs))

    variables_id, snapshot_id = record_prompt_render_artifacts(
        session=object(),
        audit_service=_AuditService(),
        audit_run=SimpleNamespace(id="run-1"),
        audit_step=SimpleNamespace(id="step-1"),
        template=SimpleNamespace(id="template-1", template_type="meta"),
        revision=SimpleNamespace(id="revision-1"),
        snapshot={"x": 1},
        rendered_prompt="rendered",
        summary_prefix="meta",
    )

    assert variables_id == "artifact-variables"
    assert snapshot_id == "artifact-snapshot"
    assert recorded_json[0][0][3] == "prompt_variables"
    assert recorded_json[1][0][3] == "prompt_snapshot"
    assert recorded_links[0][0][2] == "rendered_from"
