import json

import pytest
from pydantic import BaseModel

from app.services.providers.base import (
    ChatProvider,
    EmbeddingProvider,
    LocalCpuEmbeddingProvider,
    MockChatProvider,
)
from app.services.runtime.structured_models import (
    GenerationStructuredOutputModel,
    MetaStructuredOutputModel,
)


class _EmptyModel(BaseModel):
    pass


def test_mock_chat_provider_generate_text_prefers_latest_user_message():
    provider = MockChatProvider()

    response = provider.generate_text(
        "System prompt",
        [
            {"role": "assistant", "content": "prior"},
            {"role": "user", "content": "hello"},
        ],
        "mock-model",
        {"reply_prefix": "Echo"},
    )

    assert response.text == "Echo: hello"
    assert response.chunks == ["Echo: ", "hello "]
    assert response.raw_response == {
        "provider_kind": "mock",
        "model_name": "mock-model",
        "text": "Echo: hello",
    }
    assert response.usage.prompt_tokens == 2
    assert response.usage.completion_tokens == 2
    assert response.usage.total_tokens == 4


def test_mock_chat_provider_generate_text_falls_back_to_prompt_summary():
    provider = MockChatProvider()

    response = provider.generate_text(
        "  summarize   this prompt  ",
        [],
        "mock-model",
        {"fallback_prefix": "Summary"},
    )

    assert response.text == "Summary: summarize this prompt"


def test_mock_chat_provider_generate_structured_meta_response_extracts_context():
    provider = MockChatProvider()
    prompt = (
        "CONTEXT_JSON_START\n"
        + json.dumps(
            {
                "runtime_event": {"event_type": "chat"},
                "pending_wakeups": [{"id": "wake-1"}],
                "tag_catalog": [{"index": 1, "tag_id": "focus", "brief": "Focus topic"}],
            }
        )
        + "\nCONTEXT_JSON_END"
    )

    response = provider.generate_structured(
        prompt,
        [{"role": "user", "content": "Please remember I like tea and schedule two wakeups then cancel wakeup and focus tag"}],
        "mock-model",
        {},
        schema_model=MetaStructuredOutputModel,
        output_name="cocoon_meta_output",
    )

    assert response.raw_response["structured_output_name"] == "cocoon_meta_output"
    assert response.parsed["decision"] == "reply"
    assert response.parsed["relation_delta"] == 1
    assert response.parsed["cancel_wakeup_task_ids"] == ["wake-1"]
    assert len(response.parsed["schedule_wakeups"]) == 2
    assert response.parsed["tag_ops"] == [{"action": "add", "tag_index": 1}]


def test_mock_chat_provider_generate_structured_generator_response_for_wakeup():
    provider = MockChatProvider()
    prompt = (
        "CONTEXT_JSON_START\n"
        + json.dumps(
            {
                "runtime_event": {"event_type": "wakeup"},
                "wakeup_context": {"reason": "the user has been away"},
            }
        )
        + "\nCONTEXT_JSON_END"
    )

    response = provider.generate_structured(
        prompt,
        [],
        "mock-model",
        {"reply_prefix": "Echo"},
        schema_model=GenerationStructuredOutputModel,
        output_name="cocoon_generation_output",
    )

    assert response.parsed == {"reply_text": "Echo: I noticed the user has been away."}


def test_mock_chat_provider_extract_json_payload_handles_noise_and_invalid_input():
    provider = MockChatProvider()

    assert provider._extract_json_payload("before {\"x\": 1} after") == {"x": 1}
    assert provider._extract_json_payload("not json") == {}
    assert provider._extract_json_payload("") == {}
    assert provider._extract_context("no markers") == {}


def test_local_cpu_embedding_provider_is_deterministic_and_uses_dimensions_override():
    provider = LocalCpuEmbeddingProvider()

    response = provider.embed_texts(
        ["Alpha Beta", "Alpha Beta"],
        "local-model",
        {"dimensions": 4},
    )

    assert len(response.vectors) == 2
    assert response.vectors[0] == response.vectors[1]
    assert len(response.vectors[0]) == 4
    assert all(-1.0 <= value <= 1.0 for value in response.vectors[0])
    assert response.raw_response == {
        "provider_kind": "local_cpu",
        "model_name": "local-model",
        "dimensions": 4,
        "count": 2,
    }
    assert response.usage.prompt_tokens == 4
    assert response.usage.total_tokens == 4


def test_provider_base_abstract_methods_raise_not_implemented():
    with pytest.raises(NotImplementedError):
        ChatProvider.generate_text(object(), "", [], "model", {})
    with pytest.raises(NotImplementedError):
        ChatProvider.generate_structured(
            object(),
            "",
            [],
            "model",
            {},
            schema_model=GenerationStructuredOutputModel,
            output_name="demo",
        )
    with pytest.raises(NotImplementedError):
        EmbeddingProvider.embed_texts(object(), [], "model", {})


def test_mock_chat_provider_covers_silence_remove_tag_and_invalid_payload_paths():
    provider = MockChatProvider()

    meta_response = provider.generate_structured(
        "CONTEXT_JSON_START\nnot-json\nCONTEXT_JSON_END",
        [{"role": "user", "content": "/silent and remove focus tag"}],
        "mock-model",
        {},
        schema_model=MetaStructuredOutputModel,
        output_name="cocoon_meta_output",
    )
    fallback_response = provider.generate_structured(
        "plain prompt",
        [],
        "mock-model",
        {"fallback_prefix": "Summary"},
        schema_model=_EmptyModel,
        output_name="other_output",
    )

    assert meta_response.parsed["decision"] == "silence"
    assert meta_response.parsed["tag_ops"] == []
    assert fallback_response.text.startswith("Summary:")
    assert fallback_response.parsed == {}
    assert provider._extract_json_payload("prefix {bad json") == {}


def test_mock_chat_provider_generator_reply_uses_user_message_and_fallback_prompt():
    provider = MockChatProvider()

    user_reply = provider._generator_reply("prompt", [{"role": "user", "content": "hello"}], {"reply_prefix": "Echo"})
    fallback_reply = provider._generator_reply("  long prompt text  ", [], {"fallback_prefix": "Summary"})

    assert user_reply == '{"reply_text": "Echo: hello"}'
    assert fallback_reply.startswith('{"reply_text": "Summary: long prompt text"')
