from types import SimpleNamespace

from app.services.providers.base import ProviderStructuredResponse, ProviderUsage
from app.services.runtime.meta_node import MetaNode
from app.services.runtime.types import ContextPackage, RuntimeEvent


def _build_context(*, event_type: str = "chat", latest_user: str = "hello", target_type: str = "chat_group"):
    runtime_event = RuntimeEvent(
        event_type=event_type,
        cocoon_id=None if target_type == "chat_group" else "cocoon-1",
        chat_group_id="group-1" if target_type == "chat_group" else None,
        action_id="action-1",
        payload={"reason": "scheduled wakeup", "source_cocoon_id": "source-1"},
    )
    conversation = SimpleNamespace(selected_model_id="model-1")
    visible_messages = [
        SimpleNamespace(role="user", content=latest_user, is_retracted=False, sender_user_id="user-1"),
        SimpleNamespace(role="assistant", content="prior reply", is_retracted=True, sender_user_id=None),
    ]
    return ContextPackage(
        runtime_event=runtime_event,
        conversation=conversation,
        character=SimpleNamespace(),
        session_state=SimpleNamespace(),
        visible_messages=visible_messages,
        memory_context=[],
        external_context={
            "pending_wakeups": [{"id": "wake-1"}],
            "wakeup_context": {"reason": "idle timeout"},
            "now_utc": "2026-04-21T00:00:00Z",
        },
    )


def test_meta_node_provider_message_payload_formats_chat_group_and_retractions():
    node = MetaNode(
        prompt_service=SimpleNamespace(),
        audit_service=SimpleNamespace(),
        provider_registry=SimpleNamespace(),
    )
    context = _build_context()

    user_payload = node._provider_message_payload(context.visible_messages[0], context)
    assistant_payload = node._provider_message_payload(context.visible_messages[1], context)

    assert user_payload == {"role": "user", "content": "[sender:user-1] hello"}
    assert "[system note: this message was later retracted]" in assistant_payload["content"]


def test_meta_node_fallback_decision_covers_runtime_events():
    node = MetaNode(
        prompt_service=SimpleNamespace(),
        audit_service=SimpleNamespace(),
        provider_registry=SimpleNamespace(),
    )

    wakeup = node._fallback_decision(_build_context(event_type="wakeup"), latest_content="")
    pull = node._fallback_decision(_build_context(event_type="pull"), latest_content="")
    merge = node._fallback_decision(_build_context(event_type="merge"), latest_content="")
    silent = node._fallback_decision(_build_context(latest_user="/silent now"), latest_content="/silent now")

    assert wakeup.decision == "reply"
    assert wakeup.persona_patch == {"last_wakeup_reason": "scheduled wakeup"}
    assert pull.persona_patch == {"last_pull_source": "source-1"}
    assert merge.persona_patch == {"last_merge_source": "source-1"}
    assert silent.decision == "silence"


def test_meta_node_evaluate_builds_structured_request_and_filters_payload(monkeypatch):
    record_calls = []
    prompt_var_calls = []
    audit_calls = []

    monkeypatch.setattr(
        "app.services.runtime.meta_node.record_prompt_render_artifacts",
        lambda *args, **kwargs: record_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "app.services.runtime.meta_node.build_runtime_prompt_variables",
        lambda context, provider_capabilities: prompt_var_calls.append((context, provider_capabilities)) or {"x": 1},
    )

    class _FakeProvider:
        def __init__(self):
            self.calls = []

        def generate_structured(self, **kwargs):
            self.calls.append(kwargs)
            return ProviderStructuredResponse(
                text="raw text",
                parsed={
                    "decision": "reply",
                    "relation_delta": 2,
                    "persona_patch": {},
                    "tag_ops": [
                        {"action": "add", "tag": " focus "},
                        {"action": "remove", "tag": " "},
                    ],
                    "internal_thought": "",
                    "schedule_wakeups": [{"delay_minutes": 5}, {"reason": "follow up"}],
                    "cancel_wakeup_task_ids": ["wake-1", " ", "wake-2"],
                    "generation_brief": "brief",
                    "memory_candidates": [
                        {
                            "scope": "dialogue",
                            "summary": "pref",
                            "content": "likes tea",
                            "tags": [{"tag": " focus "}, {"tag": " "}],
                            "owner_user_id": "user-1",
                            "importance": 7,
                        },
                        {
                            "scope": "dialogue",
                            "summary": " ",
                            "content": "ignored",
                            "tags": [],
                            "importance": 1,
                        },
                    ],
                },
                raw_response={"provider": "raw"},
                usage=ProviderUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

    provider = _FakeProvider()
    provider_registry = SimpleNamespace(
        resolve_chat_provider=lambda session, model_id: (
            provider,
            SimpleNamespace(model_name="gpt-meta"),
            SimpleNamespace(kind="mock", capabilities_json={"json_mode": True}),
            {"temperature": 0.2},
        )
    )
    prompt_service = SimpleNamespace(
        render=lambda **kwargs: (
            {"id": "meta-template"},
            {"id": "meta-revision"},
            {"session_state": {"mood": "calm"}},
            "rendered meta prompt",
        )
    )
    audit_service = SimpleNamespace(record_json_artifact=lambda *args, **kwargs: audit_calls.append((args, kwargs)))
    node = MetaNode(prompt_service, audit_service, provider_registry)
    context = _build_context()

    result = node.evaluate(
        session=object(),
        context=context,
        audit_run="run-1",
        audit_step="step-1",
    )

    assert len(record_calls) == 1
    assert prompt_var_calls[0][1] == {"json_mode": True, "provider_kind": "mock", "model_name": "gpt-meta"}
    assert provider.calls[0]["model_name"] == "gpt-meta"
    assert provider.calls[0]["provider_config"] == {"temperature": 0.2}
    assert provider.calls[0]["output_name"] == "cocoon_meta_output"
    assert provider.calls[0]["messages"][0] == {"role": "user", "content": "[sender:user-1] hello"}
    assert "[system note: this message was later retracted]" in provider.calls[0]["messages"][1]["content"]
    assert '"session_state": {"mood": "calm"}' in provider.calls[0]["prompt"]
    assert result.decision == "reply"
    assert result.relation_delta == 2
    assert result.persona_patch == {"last_seen_intent": "hello"}
    assert [(item.action, item.tag) for item in result.tag_ops] == [("add", "focus")]
    assert result.internal_thought == "Structured meta decision completed."
    assert result.next_wakeup_hints == [{"delay_minutes": 5}, {"reason": "follow up"}]
    assert result.cancel_wakeup_task_ids == ["wake-1", "wake-2"]
    assert result.generation_brief == "brief"
    assert len(result.memory_candidates) == 1
    assert result.memory_candidates[0].content == "likes tea"
    assert [tag.tag for tag in result.memory_candidates[0].tags] == ["focus"]
    assert audit_calls[0][0][3] == "provider_raw_output"


def test_meta_node_evaluate_falls_back_when_provider_returns_invalid_payload(monkeypatch):
    monkeypatch.setattr("app.services.runtime.meta_node.record_prompt_render_artifacts", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.runtime.meta_node.build_runtime_prompt_variables", lambda *args, **kwargs: {})

    provider = SimpleNamespace(
        generate_structured=lambda **kwargs: ProviderStructuredResponse(
            text="ignored",
            parsed={},
            raw_response={},
            usage=ProviderUsage(),
        )
    )
    provider_registry = SimpleNamespace(
        resolve_chat_provider=lambda session, model_id: (
            provider,
            SimpleNamespace(model_name="gpt-meta"),
            SimpleNamespace(kind="mock", capabilities_json={}),
            {},
        )
    )
    prompt_service = SimpleNamespace(
        render=lambda **kwargs: (
            {"id": "meta-template"},
            {"id": "meta-revision"},
            {"session_state": {}},
            "rendered meta prompt",
        )
    )
    audit_service = SimpleNamespace(record_json_artifact=lambda *args, **kwargs: None)
    node = MetaNode(prompt_service, audit_service, provider_registry)

    result = node.evaluate(
        session=object(),
        context=_build_context(latest_user="/silent later", target_type="cocoon"),
        audit_run="run-1",
        audit_step="step-1",
    )

    assert result.decision == "silence"
    assert result.persona_patch == {"last_seen_intent": "/silent later"}
