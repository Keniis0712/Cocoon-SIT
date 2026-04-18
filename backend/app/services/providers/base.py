from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import hashlib


@dataclass
class ProviderUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ProviderTextResponse:
    text: str
    chunks: list[str]
    raw_response: dict[str, Any]
    usage: ProviderUsage


@dataclass
class ProviderEmbeddingResponse:
    vectors: list[list[float]]
    raw_response: dict[str, Any]
    usage: ProviderUsage


class ChatProvider(ABC):
    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        messages: list[dict[str, Any]],
        model_name: str,
        provider_config: dict[str, Any],
    ) -> ProviderTextResponse:
        raise NotImplementedError


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(
        self,
        texts: list[str],
        model_name: str,
        provider_config: dict[str, Any],
    ) -> ProviderEmbeddingResponse:
        raise NotImplementedError


class MockChatProvider(ChatProvider):
    def generate_text(
        self,
        prompt: str,
        messages: list[dict[str, Any]],
        model_name: str,
        provider_config: dict[str, Any],
    ) -> ProviderTextResponse:
        user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if user_message:
            reply = f"{provider_config.get('reply_prefix', 'Echo')}: {user_message}".strip()
        else:
            condensed_prompt = " ".join(prompt.strip().split())
            reply = provider_config.get("fallback_prefix", "Generated summary") + ": " + condensed_prompt[:180]
        chunks = [token + " " for token in reply.split(" ") if token]
        usage = ProviderUsage(
            prompt_tokens=max(1, len(prompt.split())),
            completion_tokens=max(1, len(reply.split())),
        )
        usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
        return ProviderTextResponse(
            text=reply,
            chunks=chunks,
            raw_response={"provider_kind": "mock", "model_name": model_name, "text": reply},
            usage=usage,
        )


class LocalCpuEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding provider used for tests and CPU-only setups."""

    def embed_texts(
        self,
        texts: list[str],
        model_name: str,
        provider_config: dict[str, Any],
    ) -> ProviderEmbeddingResponse:
        dimensions = int(provider_config.get("dimensions") or provider_config.get("dims") or 8)
        vectors = [self._embed_text(text, dimensions) for text in texts]
        usage = ProviderUsage(prompt_tokens=sum(max(1, len(text.split())) for text in texts))
        usage.total_tokens = usage.prompt_tokens
        return ProviderEmbeddingResponse(
            vectors=vectors,
            raw_response={
                "provider_kind": "local_cpu",
                "model_name": model_name,
                "dimensions": dimensions,
                "count": len(texts),
            },
            usage=usage,
        )

    def _embed_text(self, text: str, dimensions: int) -> list[float]:
        normalized = text.strip().lower() or "_"
        values: list[float] = []
        salt = 0
        while len(values) < dimensions:
            digest = hashlib.sha256(f"{salt}:{normalized}".encode("utf-8")).digest()
            for index in range(0, len(digest), 4):
                if len(values) >= dimensions:
                    break
                chunk = digest[index:index + 4]
                number = int.from_bytes(chunk, "big")
                values.append(((number % 2000) / 1000.0) - 1.0)
            salt += 1
        return values
