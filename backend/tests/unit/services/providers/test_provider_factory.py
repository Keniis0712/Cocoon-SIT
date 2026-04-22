import pytest

from app.services.providers.base import LocalCpuEmbeddingProvider, MockChatProvider
from app.services.providers.openai_compatible import OpenAICompatibleProvider
from app.services.providers.provider_factory import ProviderFactory


def test_provider_factory_resolves_known_provider_kinds():
    factory = ProviderFactory()

    assert isinstance(factory.resolve_chat_provider("mock"), MockChatProvider)
    assert isinstance(factory.resolve_chat_provider("openai_compatible"), OpenAICompatibleProvider)
    assert isinstance(factory.resolve_embedding_provider("local_cpu"), LocalCpuEmbeddingProvider)
    assert isinstance(factory.resolve_embedding_provider("openai_compatible"), OpenAICompatibleProvider)


def test_provider_factory_rejects_unknown_provider_kinds():
    factory = ProviderFactory()

    with pytest.raises(ValueError, match="Unsupported chat provider kind"):
        factory.resolve_chat_provider("missing")

    with pytest.raises(ValueError, match="Unsupported embedding provider kind"):
        factory.resolve_embedding_provider("missing")
