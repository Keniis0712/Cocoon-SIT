from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel


SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


@dataclass
class StructuredOutputInvocation:
    parsed: dict[str, Any]
    text: str
    raw_response: dict[str, Any]
    usage: dict[str, int]


def invoke_with_structured_output(
    *,
    prompt: str,
    messages: list[dict[str, Any]],
    model_name: str,
    provider_config: dict[str, Any],
    schema_model: type[SchemaModelT],
    output_name: str,
) -> StructuredOutputInvocation:
    from langchain_openai import ChatOpenAI

    base_url = provider_config.get("base_url")
    api_key = provider_config.get("api_key")
    if not base_url:
        raise ValueError("Provider base_url is required for structured output")
    if not api_key:
        raise ValueError("Provider API key is required for structured output")

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=str(base_url).rstrip("/"),
        timeout=float(provider_config.get("timeout", 60)),
        **_chat_openai_kwargs(provider_config),
    )
    structured_llm = llm.with_structured_output(
        schema_model,
        method="json_schema",
        include_raw=True,
    )
    response = structured_llm.invoke(_build_langchain_messages(prompt, messages))

    raw_message = response.get("raw")
    parsing_error = response.get("parsing_error")
    parsed_model = response.get("parsed")
    parsed = _dump_parsed_model(parsed_model)
    raw_response = {
        "structured_output_name": output_name,
        "parsed": parsed,
        "parsing_error": str(parsing_error) if parsing_error else None,
        "raw": _serialize_raw_message(raw_message),
    }
    return StructuredOutputInvocation(
        parsed=parsed,
        text=_structured_text(parsed_model, raw_message),
        raw_response=raw_response,
        usage=_extract_usage(raw_message),
    )


def _build_langchain_messages(prompt: str, messages: list[dict[str, Any]]) -> list[Any]:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    payloads: list[Any] = [SystemMessage(content=prompt)]
    for message in messages:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "")
        if role == "assistant":
            payloads.append(AIMessage(content=content))
        elif role == "system":
            payloads.append(SystemMessage(content=content))
        else:
            payloads.append(HumanMessage(content=content))
    return payloads


def _chat_openai_kwargs(provider_config: dict[str, Any]) -> dict[str, Any]:
    direct_keys = (
        "temperature",
        "max_tokens",
        "top_p",
        "frequency_penalty",
        "presence_penalty",
    )
    kwargs = {key: provider_config[key] for key in direct_keys if key in provider_config}
    excluded = {"base_url", "api_key", "timeout", *direct_keys}
    model_kwargs = {key: value for key, value in provider_config.items() if key not in excluded}
    if model_kwargs:
        kwargs["model_kwargs"] = model_kwargs
    return kwargs


def _dump_parsed_model(parsed_model: Any) -> dict[str, Any]:
    if isinstance(parsed_model, BaseModel):
        return parsed_model.model_dump(mode="json")
    if isinstance(parsed_model, dict):
        return parsed_model
    return {}


def _structured_text(parsed_model: Any, raw_message: Any) -> str:
    if isinstance(parsed_model, BaseModel):
        if hasattr(parsed_model, "reply_text"):
            reply_text = getattr(parsed_model, "reply_text")
            if isinstance(reply_text, str):
                return reply_text
        return json.dumps(parsed_model.model_dump(mode="json"), ensure_ascii=False)
    if raw_message is not None:
        content = getattr(raw_message, "content", "")
        if isinstance(content, list):
            return "".join(str(item) for item in content).strip()
        return str(content).strip()
    return ""


def _serialize_raw_message(raw_message: Any) -> dict[str, Any]:
    if raw_message is None:
        return {}
    return {
        "content": getattr(raw_message, "content", None),
        "additional_kwargs": getattr(raw_message, "additional_kwargs", {}),
        "response_metadata": getattr(raw_message, "response_metadata", {}),
        "usage_metadata": getattr(raw_message, "usage_metadata", {}),
    }


def _extract_usage(raw_message: Any) -> dict[str, int]:
    usage_metadata = getattr(raw_message, "usage_metadata", {}) or {}
    response_metadata = getattr(raw_message, "response_metadata", {}) or {}
    token_usage = response_metadata.get("token_usage", {}) if isinstance(response_metadata, dict) else {}

    prompt_tokens = int(
        usage_metadata.get("input_tokens")
        or token_usage.get("prompt_tokens")
        or 0
    )
    completion_tokens = int(
        usage_metadata.get("output_tokens")
        or token_usage.get("completion_tokens")
        or 0
    )
    total_tokens = int(
        usage_metadata.get("total_tokens")
        or token_usage.get("total_tokens")
        or prompt_tokens + completion_tokens
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
