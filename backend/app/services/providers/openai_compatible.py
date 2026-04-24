from typing import Any
import logging
import time

import httpx
from pydantic import BaseModel

from app.services.providers.base import (
    ChatProvider,
    EmbeddingProvider,
    ProviderEmbeddingResponse,
    ProviderStructuredResponse,
    ProviderTextResponse,
    ProviderUsage,
)
from app.services.runtime.structured_output import invoke_with_structured_output


class OpenAICompatibleProvider(ChatProvider, EmbeddingProvider):
    logger = logging.getLogger(__name__)

    def _embedding_retry_count(self, provider_config: dict[str, Any]) -> int:
        raw_value = provider_config.get("embedding_max_retries", provider_config.get("embedding_retry_count", 0))
        try:
            return max(0, int(raw_value or 0))
        except (TypeError, ValueError):
            return 0

    def _embedding_timeout(self, provider_config: dict[str, Any]) -> float:
        raw_value = provider_config.get("embedding_timeout", provider_config.get("timeout", 60))
        try:
            timeout = float(raw_value or 60)
        except (TypeError, ValueError):
            return 60.0
        return timeout if timeout > 0 else 60.0

    def _embedding_retry_delay(self, attempt_index: int, *, exponential_backoff: bool) -> float:
        base_delay = 0.5
        if not exponential_backoff:
            return base_delay
        return min(base_delay * (2 ** max(attempt_index - 1, 0)), 8.0)

    def generate_text(
        self,
        prompt: str,
        messages: list[dict[str, Any]],
        model_name: str,
        provider_config: dict[str, Any],
    ) -> ProviderTextResponse:
        base_url = provider_config.get("base_url")
        api_key = provider_config.get("api_key")
        if not base_url:
            raise ValueError("Provider base_url is required for openai_compatible providers")
        if not api_key:
            raise ValueError("Provider API key is required for openai_compatible providers")
        timeout = float(provider_config.get("timeout", 60))
        request_messages = [{"role": "system", "content": prompt}, *messages]
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "messages": request_messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )
        text = str(content).strip()
        chunks = [token + " " for token in text.split(" ") if token]
        usage_payload = data.get("usage", {}) if isinstance(data, dict) else {}
        usage = ProviderUsage(
            prompt_tokens=int(usage_payload.get("prompt_tokens") or 0),
            completion_tokens=int(usage_payload.get("completion_tokens") or 0),
            total_tokens=int(usage_payload.get("total_tokens") or 0),
        )
        if usage.total_tokens == 0:
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
        return ProviderTextResponse(
            text=text,
            chunks=chunks,
            raw_response=data if isinstance(data, dict) else {"response": data},
            usage=usage,
        )

    def generate_structured(
        self,
        prompt: str,
        messages: list[dict[str, Any]],
        model_name: str,
        provider_config: dict[str, Any],
        *,
        schema_model: type[BaseModel],
        output_name: str,
    ) -> ProviderStructuredResponse:
        self.logger.info(
            "OpenAI-compatible structured generation start model=%s base_url=%s method=%s message_count=%s output_name=%s",
            model_name,
            provider_config.get("base_url"),
            provider_config.get("structured_output_method", "tool_calling"),
            len(messages),
            output_name,
        )
        result = invoke_with_structured_output(
            prompt=prompt,
            messages=messages,
            model_name=model_name,
            provider_config=provider_config,
            schema_model=schema_model,
            output_name=output_name,
        )
        self.logger.info(
            "OpenAI-compatible structured generation complete model=%s output_name=%s parsed_keys=%s prompt_tokens=%s completion_tokens=%s",
            model_name,
            output_name,
            sorted(result.parsed.keys()),
            result.usage["prompt_tokens"],
            result.usage["completion_tokens"],
        )
        usage = ProviderUsage(
            prompt_tokens=result.usage["prompt_tokens"],
            completion_tokens=result.usage["completion_tokens"],
            total_tokens=result.usage["total_tokens"],
        )
        return ProviderStructuredResponse(
            text=result.text,
            parsed=result.parsed,
            raw_response=result.raw_response,
            usage=usage,
        )

    def embed_texts(
        self,
        texts: list[str],
        model_name: str,
        provider_config: dict[str, Any],
    ) -> ProviderEmbeddingResponse:
        base_url = provider_config.get("base_url")
        api_key = provider_config.get("api_key")
        if not base_url:
            raise ValueError("Provider base_url is required for openai_compatible providers")
        if not api_key:
            raise ValueError("Provider API key is required for openai_compatible providers")
        timeout = self._embedding_timeout(provider_config)
        max_retries = self._embedding_retry_count(provider_config)
        exponential_backoff = bool(provider_config.get("embedding_exponential_backoff", False))
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        f"{base_url.rstrip('/')}/embeddings",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model_name,
                            "input": texts,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                break
            except httpx.HTTPError:
                if attempt >= max_retries:
                    raise
                delay = self._embedding_retry_delay(attempt + 1, exponential_backoff=exponential_backoff)
                self.logger.warning(
                    "OpenAI-compatible embedding request failed; retrying model=%s attempt=%s max_retries=%s delay_seconds=%s",
                    model_name,
                    attempt + 1,
                    max_retries,
                    delay,
                    exc_info=True,
                )
                time.sleep(delay)
        items = data.get("data", []) if isinstance(data, dict) else []
        vectors = [[float(value) for value in item.get("embedding", [])] for item in items]
        usage_payload = data.get("usage", {}) if isinstance(data, dict) else {}
        usage = ProviderUsage(
            prompt_tokens=int(usage_payload.get("prompt_tokens") or 0),
            total_tokens=int(usage_payload.get("total_tokens") or 0),
        )
        if usage.total_tokens == 0:
            usage.total_tokens = usage.prompt_tokens
        return ProviderEmbeddingResponse(
            vectors=vectors,
            raw_response=data if isinstance(data, dict) else {"response": data},
            usage=usage,
        )
