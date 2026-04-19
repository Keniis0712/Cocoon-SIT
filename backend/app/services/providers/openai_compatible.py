from typing import Any

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
        schema: dict[str, Any],
        schema_model: type[BaseModel] | None = None,
        output_name: str,
    ) -> ProviderStructuredResponse:
        if schema_model is None:
            raise ValueError("schema_model is required for native structured output")
        result = invoke_with_structured_output(
            prompt=prompt,
            messages=messages,
            model_name=model_name,
            provider_config=provider_config,
            schema_model=schema_model,
            output_name=output_name,
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
        timeout = float(provider_config.get("timeout", 60))
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
