from types import SimpleNamespace

from app.services.providers.base import ProviderStructuredResponse, ProviderUsage
from app.services.runtime.generation.generator_node import GeneratorNode
from app.services.runtime.types import ContextPackage, MetaDecision, RuntimeEvent


def _build_context() -> ContextPackage:
    cocoon = SimpleNamespace(selected_model_id="model-1")
    return ContextPackage(
        runtime_event=RuntimeEvent(
            event_type="chat",
            cocoon_id="cocoon-1",
            chat_group_id=None,
            action_id="action-1",
            payload={"reason": "user_message", "timezone": "Asia/Shanghai"},
        ),
        conversation=cocoon,
        character=SimpleNamespace(),
        session_state=SimpleNamespace(),
        visible_messages=[],
        memory_context=[],
        external_context={
            "wakeup_context": {"reason": "scheduled reminder"},
            "pending_wakeups": [{"id": "wake-1"}],
        },
    )


def test_build_chunks_returns_tokens_and_skips_empty_text():
    node = GeneratorNode(
        prompt_assembly_service=SimpleNamespace(),
        provider_registry=SimpleNamespace(),
        audit_service=SimpleNamespace(),
    )

    assert node._build_chunks("hello world") == ["hello ", "world "]
    assert node._build_chunks("") == []


def test_generator_node_generate_records_artifacts_and_uses_structured_fallback(monkeypatch):
    record_calls = []
    audit_calls = []

    monkeypatch.setattr(
        "app.services.runtime.generation.generator_node.record_prompt_render_artifacts",
        lambda *args, **kwargs: record_calls.append((args, kwargs)),
    )

    class _FakeProvider:
        def __init__(self):
            self.calls = []

        def generate_structured(self, **kwargs):
            self.calls.append(kwargs)
            return ProviderStructuredResponse(
                text=" Generated reply ",
                parsed={},
                raw_response={"provider": "raw"},
                usage=ProviderUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
            )

    provider = _FakeProvider()
    provider_registry = SimpleNamespace(
        resolve_chat_provider=lambda session, model_id: (
            provider,
            SimpleNamespace(model_name="gpt-unit"),
            SimpleNamespace(kind="mock", capabilities_json={"streaming": True}),
            {"temperature": 0.4},
        )
    )
    assembly = SimpleNamespace(
        system=SimpleNamespace(
            template={"id": "system-template"},
            revision={"id": "system-revision"},
            snapshot={"kind": "system"},
            rendered_prompt="system rendered",
            summary_prefix="system",
        ),
        event=SimpleNamespace(
            template={"id": "event-template"},
            revision={"id": "event-revision"},
            snapshot={"kind": "event"},
            rendered_prompt="event rendered",
            summary_prefix="event",
        ),
        combined_prompt="combined prompt",
        messages=[{"role": "user", "content": "hello"}],
    )
    prompt_assembly_service = SimpleNamespace(build=lambda **kwargs: assembly)
    audit_service = SimpleNamespace(record_json_artifact=lambda *args, **kwargs: audit_calls.append((args, kwargs)))
    node = GeneratorNode(prompt_assembly_service, provider_registry, audit_service)

    result = node.generate(
        session=object(),
        context=_build_context(),
        meta=MetaDecision(
            decision="reply",
            relation_delta=1,
            persona_patch={},
            tag_ops=[],
            internal_thought="x",
            generation_brief="stay concise",
        ),
        audit_run="run-1",
        audit_step="step-1",
    )

    assert len(record_calls) == 2
    assert provider.calls[0]["model_name"] == "gpt-unit"
    assert provider.calls[0]["provider_config"] == {"temperature": 0.4}
    assert provider.calls[0]["output_name"] == "cocoon_generation_output"
    assert provider.calls[0]["messages"] == [{"role": "user", "content": "hello"}]
    assert "CONTEXT_JSON_START" in provider.calls[0]["prompt"]
    assert "Current local time:" in provider.calls[0]["prompt"]
    assert "Asia/Shanghai" in provider.calls[0]["prompt"]
    assert '"generation_brief": "stay concise"' in provider.calls[0]["prompt"]
    assert result.reply_text == "Generated reply"
    assert result.chunks == ["Generated ", "reply "]
    assert result.structured_output == {"reply_text": "Generated reply"}
    assert result.usage == {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}
    assert result.provider_kind == "mock"
    assert result.model_name == "gpt-unit"
    assert audit_calls[0][0][3] == "provider_raw_output"


def test_generator_node_build_structured_prompt_includes_runtime_context():
    node = GeneratorNode(
        prompt_assembly_service=SimpleNamespace(),
        provider_registry=SimpleNamespace(),
        audit_service=SimpleNamespace(),
    )
    context = _build_context()
    meta = MetaDecision(
        decision="reply",
        relation_delta=0,
        persona_patch={},
        tag_ops=[],
        internal_thought="x",
        generation_brief="brief",
    )

    prompt = node._build_structured_prompt(
        context,
        "rendered prompt",
        meta,
        prompt_snapshot={
            "runtime_event": {"event_type": "chat", "target_type": "cocoon"},
            "wakeup_context": {"reason": "scheduled reminder"},
            "pending_wakeups": [{"id": "wake-1", "reason": "later", "status": "queued", "has_payload": False, "run_at": None}],
        },
    )

    assert "PROMPT_TEXT_START" in prompt
    assert "rendered prompt" in prompt
    assert "META_DECISION_GUIDANCE_START" in prompt
    assert "brief" in prompt
    assert "Current local time:" in prompt
    assert '"target_type": "cocoon"' in prompt
    assert '"current_time": {"timezone": "Asia/Shanghai"' in prompt
    assert '"pending_wakeups": [{"id": "wake-1", "reason": "later", "status": "queued"}]' in prompt
    assert "target_id" not in prompt
