from types import SimpleNamespace

import pytest

from app.services.providers.openai_compatible import OpenAICompatibleProvider
from app.services.runtime.structured_output import StructuredOutputInvocation


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, *, payload):
        self.payload = payload
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *, headers, json):
        self.requests.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse(self.payload)


def test_generate_text_requires_base_url():
    provider = OpenAICompatibleProvider()

    with pytest.raises(ValueError, match="base_url"):
        provider.generate_text("prompt", [], "model", {"api_key": "secret"})


def test_generate_text_requires_api_key():
    provider = OpenAICompatibleProvider()

    with pytest.raises(ValueError, match="API key"):
        provider.generate_text("prompt", [], "model", {"base_url": "https://example.com"})


def test_generate_text_normalizes_content_and_usage(monkeypatch):
    provider = OpenAICompatibleProvider()
    fake_client = _FakeClient(
        payload={
            "choices": [
                {
                    "message": {
                        "content": [
                            {"text": "Hello"},
                            {"text": " world"},
                        ]
                    }
                }
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 3},
        }
    )

    monkeypatch.setattr(
        "app.services.providers.openai_compatible.httpx.Client",
        lambda timeout: fake_client,
    )

    response = provider.generate_text(
        "system prompt",
        [{"role": "user", "content": "Hi"}],
        "gpt-test",
        {"base_url": "https://example.com/", "api_key": "secret", "timeout": 12},
    )

    assert response.text == "Hello world"
    assert response.chunks == ["Hello ", "world "]
    assert response.usage.prompt_tokens == 4
    assert response.usage.completion_tokens == 3
    assert response.usage.total_tokens == 7
    assert fake_client.requests == [
        {
            "url": "https://example.com/chat/completions",
            "headers": {
                "Authorization": "Bearer secret",
                "Content-Type": "application/json",
            },
            "json": {
                "model": "gpt-test",
                "messages": [
                    {"role": "system", "content": "system prompt"},
                    {"role": "user", "content": "Hi"},
                ],
                "stream": False,
            },
        }
    ]


def test_generate_structured_wraps_structured_output_result(monkeypatch):
    provider = OpenAICompatibleProvider()

    monkeypatch.setattr(
        "app.services.providers.openai_compatible.invoke_with_structured_output",
        lambda **kwargs: StructuredOutputInvocation(
            parsed={"reply_text": "Hello"},
            text="Hello",
            raw_response={"provider": "fake"},
            usage={"prompt_tokens": 2, "completion_tokens": 4, "total_tokens": 6},
        ),
    )

    result = provider.generate_structured(
        "prompt",
        [{"role": "user", "content": "hi"}],
        "gpt-test",
        {"base_url": "https://example.com", "api_key": "secret"},
        schema_model=SimpleNamespace,
        output_name="demo",
    )

    assert result.text == "Hello"
    assert result.parsed == {"reply_text": "Hello"}
    assert result.raw_response == {"provider": "fake"}
    assert result.usage.prompt_tokens == 2
    assert result.usage.completion_tokens == 4
    assert result.usage.total_tokens == 6


def test_embed_texts_normalizes_vectors_and_usage(monkeypatch):
    provider = OpenAICompatibleProvider()
    fake_client = _FakeClient(
        payload={
            "data": [
                {"embedding": [1, 2.5, "3"]},
                {"embedding": [0, -1]},
            ],
            "usage": {"prompt_tokens": 5},
        }
    )

    monkeypatch.setattr(
        "app.services.providers.openai_compatible.httpx.Client",
        lambda timeout: fake_client,
    )

    response = provider.embed_texts(
        ["alpha", "beta"],
        "text-embedding-test",
        {"base_url": "https://example.com/", "api_key": "secret"},
    )

    assert response.vectors == [[1.0, 2.5, 3.0], [0.0, -1.0]]
    assert response.usage.prompt_tokens == 5
    assert response.usage.total_tokens == 5
    assert fake_client.requests == [
        {
            "url": "https://example.com/embeddings",
            "headers": {
                "Authorization": "Bearer secret",
                "Content-Type": "application/json",
            },
            "json": {
                "model": "text-embedding-test",
                "input": ["alpha", "beta"],
            },
        }
    ]
