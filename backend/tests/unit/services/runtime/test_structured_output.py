import sys
from types import ModuleType, SimpleNamespace

from pydantic import BaseModel

from app.services.runtime.structured_output import (
    _chat_openai_kwargs,
    _extract_usage,
    _structured_text,
    invoke_with_structured_output,
)


class _ReplyModel(BaseModel):
    reply_text: str
    mood: str = "neutral"


class _OtherModel(BaseModel):
    value: int


def test_chat_openai_kwargs_separates_direct_and_model_kwargs():
    kwargs = _chat_openai_kwargs(
        {
            "base_url": "https://example.com",
            "api_key": "secret",
            "timeout": 30,
            "temperature": 0.2,
            "max_tokens": 128,
            "custom_flag": True,
        }
    )

    assert kwargs == {
        "temperature": 0.2,
        "max_tokens": 128,
        "model_kwargs": {"custom_flag": True},
    }


def test_structured_text_prefers_reply_text_and_falls_back_to_raw_content():
    assert _structured_text(_ReplyModel(reply_text="Hi there"), raw_message=None) == "Hi there"
    assert _structured_text(_OtherModel(value=3), raw_message=None) == '{"value": 3}'
    assert _structured_text(None, SimpleNamespace(content=["one", " ", "two"])) == "one two"
    assert _structured_text(None, SimpleNamespace(content=" plain text ")) == "plain text"


def test_extract_usage_prefers_usage_metadata_and_falls_back_to_response_metadata():
    raw_message = SimpleNamespace(
        usage_metadata={"input_tokens": 5, "output_tokens": 7},
        response_metadata={"token_usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}},
    )
    fallback_message = SimpleNamespace(
        usage_metadata={},
        response_metadata={"token_usage": {"prompt_tokens": 4, "completion_tokens": 6}},
    )

    assert _extract_usage(raw_message) == {
        "prompt_tokens": 5,
        "completion_tokens": 7,
        "total_tokens": 3,
    }
    assert _extract_usage(fallback_message) == {
        "prompt_tokens": 4,
        "completion_tokens": 6,
        "total_tokens": 10,
    }


def test_invoke_with_structured_output_requires_provider_credentials(monkeypatch):
    fake_openai = ModuleType("langchain_openai")
    fake_openai.ChatOpenAI = object
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_openai)

    try:
        invoke_with_structured_output(
            prompt="prompt",
            messages=[],
            model_name="model",
            provider_config={"api_key": "secret"},
            schema_model=_ReplyModel,
            output_name="demo",
        )
    except ValueError as exc:
        assert "base_url" in str(exc)
    else:
        raise AssertionError("Expected base_url validation error")

    try:
        invoke_with_structured_output(
            prompt="prompt",
            messages=[],
            model_name="model",
            provider_config={"base_url": "https://example.com"},
            schema_model=_ReplyModel,
            output_name="demo",
        )
    except ValueError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Expected api_key validation error")


def test_invoke_with_structured_output_uses_langchain_adapter(monkeypatch):
    fake_messages = ModuleType("langchain_core.messages")

    class _FakeSystemMessage:
        def __init__(self, content):
            self.content = content
            self.role = "system"

    class _FakeHumanMessage:
        def __init__(self, content):
            self.content = content
            self.role = "user"

    class _FakeAIMessage:
        def __init__(self, content, **kwargs):
            self.content = content
            self.additional_kwargs = kwargs.get("additional_kwargs", {})
            self.response_metadata = kwargs.get("response_metadata", {})
            self.usage_metadata = kwargs.get("usage_metadata", {})
            self.role = "assistant"

    fake_messages.SystemMessage = _FakeSystemMessage
    fake_messages.HumanMessage = _FakeHumanMessage
    fake_messages.AIMessage = _FakeAIMessage

    calls = {}

    class _FakeStructuredLLM:
        def invoke(self, payload):
            calls["payload"] = payload
            return {
                "raw": _FakeAIMessage(
                    content=["raw", " text"],
                    additional_kwargs={"finish_reason": "stop"},
                    response_metadata={"token_usage": {"prompt_tokens": 2, "completion_tokens": 3}},
                    usage_metadata={},
                ),
                "parsing_error": RuntimeError("bad field"),
                "parsed": _ReplyModel(reply_text="Structured hello", mood="calm"),
            }

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls["init_kwargs"] = kwargs

        def with_structured_output(self, schema_model, *, method, include_raw):
            calls["schema_model"] = schema_model
            calls["method"] = method
            calls["include_raw"] = include_raw
            return _FakeStructuredLLM()

    fake_openai = ModuleType("langchain_openai")
    fake_openai.ChatOpenAI = _FakeChatOpenAI

    monkeypatch.setitem(sys.modules, "langchain_core.messages", fake_messages)
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_openai)

    result = invoke_with_structured_output(
        prompt="System prompt",
        messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "prior"},
            {"role": "system", "content": "extra"},
        ],
        model_name="gpt-test",
        provider_config={
            "base_url": "https://example.com/",
            "api_key": "secret",
            "timeout": 12,
            "temperature": 0.3,
            "custom_flag": True,
        },
        schema_model=_ReplyModel,
        output_name="demo_output",
    )

    assert calls["init_kwargs"] == {
        "model": "gpt-test",
        "api_key": "secret",
        "base_url": "https://example.com",
        "timeout": 12.0,
        "temperature": 0.3,
        "model_kwargs": {"custom_flag": True},
    }
    assert calls["schema_model"] is _ReplyModel
    assert calls["method"] == "json_schema"
    assert calls["include_raw"] is True
    assert [item.role for item in calls["payload"]] == ["system", "user", "assistant", "system"]
    assert [item.content for item in calls["payload"]] == ["System prompt", "hello", "prior", "extra"]
    assert result.parsed == {"reply_text": "Structured hello", "mood": "calm"}
    assert result.text == "Structured hello"
    assert result.raw_response == {
        "structured_output_name": "demo_output",
        "parsed": {"reply_text": "Structured hello", "mood": "calm"},
        "parsing_error": "bad field",
        "raw": {
            "content": ["raw", " text"],
            "additional_kwargs": {"finish_reason": "stop"},
            "response_metadata": {"token_usage": {"prompt_tokens": 2, "completion_tokens": 3}},
            "usage_metadata": {},
        },
    }
    assert result.usage == {
        "prompt_tokens": 2,
        "completion_tokens": 3,
        "total_tokens": 5,
    }
