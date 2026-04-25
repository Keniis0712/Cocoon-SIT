from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import hashlib
import json

from pydantic import BaseModel


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


@dataclass
class ProviderStructuredResponse:
    text: str
    parsed: dict[str, Any]
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

    @abstractmethod
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
        return self._build_response(reply, prompt, model_name)

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
        if output_name == "cocoon_meta_output":
            text = self._meta_reply(prompt, messages)
        elif output_name == "cocoon_compaction_output":
            text = self._compaction_reply(prompt)
        elif output_name == "cocoon_generation_output":
            text = self._generator_reply(prompt, messages, provider_config)
        else:
            text = self.generate_text(
                prompt=prompt,
                messages=messages,
                model_name=model_name,
                provider_config=provider_config,
            ).text
        response = self._build_response(text, prompt, model_name)
        parsed = self._extract_json_payload(response.text)
        parsed = schema_model.model_validate(parsed).model_dump(mode="json")
        return ProviderStructuredResponse(
            text=response.text,
            parsed=parsed,
            raw_response={
                **response.raw_response,
                "structured_output_name": output_name,
            },
            usage=response.usage,
        )

    def _build_response(self, reply: str, prompt: str, model_name: str) -> ProviderTextResponse:
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

    def _extract_context(self, prompt: str) -> dict[str, Any]:
        for start_marker, end_marker in (
            ("CONTEXT_JSON_START", "CONTEXT_JSON_END"),
            ("COMPACTION_CONTEXT_JSON_START", "COMPACTION_CONTEXT_JSON_END"),
        ):
            start = prompt.find(start_marker)
            end = prompt.find(end_marker)
            if start < 0 or end <= start:
                continue
            raw = prompt[start + len(start_marker):end].strip()
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload
        return {}

    def _meta_reply(self, prompt: str, messages: list[dict[str, Any]]) -> str:
        context = self._extract_context(prompt)
        runtime_event = context.get("runtime_event") or {}
        pending_wakeups = context.get("pending_wakeups") or []
        tag_catalog = context.get("tag_catalog") or []
        wakeup_context = context.get("wakeup_context") or {}
        latest_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        decision = "reply"
        wakeups: list[dict[str, Any]] = []
        cancel_ids: list[str] = []
        if "/silent" in latest_user:
            decision = "silence"
        if "schedule two wakeups" in latest_user.lower():
            wakeups = [
                {"delay_minutes": 10, "reason": "First follow-up after the conversation stopped."},
                {"delay_minutes": 30, "reason": "Second follow-up if the user is still away."},
            ]
        if "cancel wakeup" in latest_user.lower() and pending_wakeups:
            cancel_ids = [str(pending_wakeups[0].get("id"))]
        lower_user = latest_user.lower()
        if runtime_event.get("event_type") == "wakeup" and str(runtime_event.get("trigger_kind")) == "idle_timeout":
            decision = "reply"
        first_tag_index = 0
        if isinstance(tag_catalog, list):
            for item in tag_catalog:
                if isinstance(item, dict) and isinstance(item.get("index"), int):
                    first_tag_index = int(item["index"])
                    break
        tag_ops: list[dict[str, Any]] = []
        if first_tag_index > 0 and "focus tag" in lower_user:
            tag_ops.append({"action": "add", "tag_index": first_tag_index})
        if first_tag_index > 0 and "remove focus tag" in lower_user:
            tag_ops.append({"action": "remove", "tag_index": first_tag_index})
        return json.dumps(
            {
                "decision": decision,
                "relation_delta": 1 if latest_user else 0,
                "persona_patch": {"last_seen_intent": latest_user[:120]},
                "tag_ops": tag_ops,
                "internal_thought": "Mock structured meta output.",
                "event_summary": (
                    str(runtime_event.get("reason") or wakeup_context.get("reason") or "Wakeup evaluated without reply")
                    if decision == "silence" and runtime_event.get("event_type") == "wakeup"
                    else None
                ),
                "schedule_wakeups": wakeups,
                "cancel_wakeup_task_ids": cancel_ids,
                "generation_brief": latest_user[:200] or None,
            },
            ensure_ascii=False,
        )

    def _compaction_reply(self, prompt: str) -> str:
        context = self._extract_context(prompt)
        visible_messages = context.get("visible_messages") or []
        tag_catalog = context.get("tag_catalog") or []
        summary = "No durable memory extracted."
        items: list[dict[str, Any]] = []
        if isinstance(visible_messages, list) and visible_messages:
            last_item = visible_messages[-1] if isinstance(visible_messages[-1], dict) else {}
            content = str(last_item.get("content") or "").strip() or "Conversation summary"
            summary = content[:200]
            item: dict[str, Any] = {
                "scope": "summary",
                "summary": content[:120] or "Conversation summary",
                "content": content,
                "tag_indexes": [],
                "importance": 6,
            }
            if isinstance(tag_catalog, list):
                first = next(
                    (
                        int(tag.get("index"))
                        for tag in tag_catalog
                        if isinstance(tag, dict) and isinstance(tag.get("index"), int)
                    ),
                    0,
                )
                if first > 0:
                    item["tag_indexes"] = [first]
            items.append(item)
        return json.dumps({"summary": summary, "long_term_memories": items}, ensure_ascii=False)

    def _generator_reply(
        self,
        prompt: str,
        messages: list[dict[str, Any]],
        provider_config: dict[str, Any],
    ) -> str:
        context = self._extract_context(prompt)
        runtime_event = context.get("runtime_event") or {}
        wakeup_context = context.get("wakeup_context") or {}
        user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if runtime_event.get("event_type") == "wakeup":
            silence_duration = wakeup_context.get("idle_summary") or wakeup_context.get("reason") or "the conversation has been quiet"
            reply_text = f"{provider_config.get('reply_prefix', 'Echo')}: I noticed {silence_duration}."
        elif user_message:
            reply_text = f"{provider_config.get('reply_prefix', 'Echo')}: {user_message}".strip()
        else:
            condensed_prompt = " ".join(prompt.strip().split())
            reply_text = provider_config.get("fallback_prefix", "Generated summary") + ": " + condensed_prompt[:180]
        return json.dumps({"reply_text": reply_text}, ensure_ascii=False)

    def _extract_json_payload(self, text: str) -> dict[str, Any]:
        raw = text.strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end <= start:
                return {}
            try:
                payload = json.loads(raw[start:end + 1])
            except Exception:
                return {}
        return payload if isinstance(payload, dict) else {}


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
