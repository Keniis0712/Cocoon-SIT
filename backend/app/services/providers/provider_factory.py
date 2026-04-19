"""Concrete provider implementation factory."""

from __future__ import annotations

from app.services.providers.base import (
    ChatProvider,
    EmbeddingProvider,
    LocalCpuEmbeddingProvider,
    MockChatProvider,
)
from app.services.providers.openai_compatible import OpenAICompatibleProvider


class ProviderFactory:
    """Returns concrete provider implementations from provider-kind strings."""

    def __init__(self) -> None:
        self._chat_providers: dict[str, ChatProvider] = {
            "mock": MockChatProvider(),
            "openai_compatible": OpenAICompatibleProvider(),
        }
        self._embedding_providers: dict[str, EmbeddingProvider] = {
            "local_cpu": LocalCpuEmbeddingProvider(),
            "openai_compatible": OpenAICompatibleProvider(),
        }

    def resolve_chat_provider(self, provider_kind: str) -> ChatProvider:
        """Return the provider implementation for the given kind."""
        provider = self._chat_providers.get(provider_kind)
        if provider is None:
            raise ValueError(f"Unsupported chat provider kind: {provider_kind}")
        return provider

    def resolve_embedding_provider(self, provider_kind: str) -> EmbeddingProvider:
        """Return the embedding-provider implementation for the given kind."""
        provider = self._embedding_providers.get(provider_kind)
        if provider is None:
            raise ValueError(f"Unsupported embedding provider kind: {provider_kind}")
        return provider
