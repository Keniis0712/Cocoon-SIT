"""Runtime meta-decision service."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.services.audit.service import AuditService
from app.services.prompts.service import PromptTemplateService
from app.services.runtime.prompting.prompting import (
    build_provider_message_payload,
    build_structured_prompt_context,
    build_runtime_prompt_variables,
    record_prompt_render_artifacts,
)
from app.services.runtime.structured_models import MetaStructuredOutputModel, ScheduledWakeupModel
from app.services.runtime.types import (
    ContextPackage,
    FactCacheOperation,
    MemoryOperation,
    MetaDecision,
    TagOperation,
    TagReference,
)
from app.services.providers.registry import ProviderRegistry


class MetaNode:
    """Evaluates context and decides whether the runtime should reply or stay silent."""

    def __init__(
        self,
        prompt_service: PromptTemplateService,
        audit_service: AuditService,
        provider_registry: ProviderRegistry,
    ) -> None:
        self.prompt_service = prompt_service
        self.audit_service = audit_service
        self.provider_registry = provider_registry

    def evaluate(
        self,
        session: Session,
        context: ContextPackage,
        audit_run,
        audit_step,
    ) -> MetaDecision:
        provider, model, provider_record, runtime_provider_config = self.provider_registry.resolve_chat_provider(
            session,
            context.cocoon.selected_model_id,
        )
        template, revision, snapshot, rendered_prompt = self.prompt_service.render(
            session=session,
            template_type="meta",
            variables=build_runtime_prompt_variables(
                context,
                provider_capabilities=provider_record.capabilities_json,
                include_wakeup_context=True,
            ),
        )
        record_prompt_render_artifacts(
            session,
            self.audit_service,
            audit_run,
            audit_step,
            template,
            revision,
            snapshot,
            rendered_prompt,
            summary_prefix="meta",
        )
        latest_user = next(
            (
                message
                for message in reversed(context.visible_messages)
                if message.role == "user" and not message.is_retracted
            ),
            None,
        )
        latest_content = latest_user.content if latest_user else ""
        provider_prompt = self._build_structured_prompt(context, rendered_prompt, snapshot)
        response = provider.generate_structured(
            prompt=provider_prompt,
            messages=[build_provider_message_payload(message, context) for message in context.visible_messages],
            model_name=model.model_name,
            provider_config=runtime_provider_config,
            schema_model=MetaStructuredOutputModel,
            output_name="cocoon_meta_output",
        )
        self.audit_service.record_json_artifact(
            session,
            audit_run,
            audit_step,
            "provider_raw_output",
            response.raw_response,
            summary="Provider raw meta output",
            metadata_json={
                "provider_kind": provider_record.kind,
                "model_name": model.model_name,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )
        if not response.parsed:
            return self._fallback_decision(context, latest_content)
        try:
            parsed = MetaStructuredOutputModel.model_validate(response.parsed)
        except Exception:
            return self._fallback_decision(context, latest_content)
        relation_delta_int = int(parsed.relation_delta if latest_content or parsed.relation_delta else 0)
        internal_thought = str(parsed.internal_thought or "Structured meta decision completed.")
        event_summary = self._normalize_event_summary(
            context,
            decision=parsed.decision,
            raw_summary=parsed.event_summary,
        )
        return MetaDecision(
            decision=parsed.decision,
            relation_delta=relation_delta_int + int(parsed.session_update.relation_delta or 0),
            persona_patch=(parsed.persona_patch or {"last_seen_intent": latest_content[:120]})
            | dict(parsed.session_update.persona_patch or {}),
            tag_ops=self._normalize_tag_ops(parsed.tag_ops, parsed.session_update.tag_ops),
            internal_thought=internal_thought,
            event_summary=event_summary,
            next_wakeup_hints=self._normalize_wakeup_hints(parsed.schedule_wakeups),
            cancel_wakeup_task_ids=[str(item) for item in parsed.cancel_wakeup_task_ids if str(item).strip()],
            generation_brief=parsed.generation_brief,
            used_memory_ids=[str(item) for item in parsed.used_memory_ids if str(item).strip()],
            session_update=parsed.session_update.model_dump(exclude_none=True),
            task_state_update=parsed.task_state_update.model_dump(exclude_none=True),
            fact_cache_ops=self._normalize_fact_cache_ops(parsed.fact_cache_ops),
            memory_ops=self._normalize_memory_ops(parsed.memory_ops),
            request_mode="meta_reply",
        )

    def _normalize_wakeup_hints(
        self,
        items: list[ScheduledWakeupModel | dict[str, object]],
    ) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for item in items:
            if isinstance(item, ScheduledWakeupModel):
                normalized.append(item.model_dump(exclude_none=True))
                continue
            try:
                parsed = ScheduledWakeupModel.model_validate(item)
            except Exception:
                continue
            normalized.append(parsed.model_dump(exclude_none=True))
        return normalized

    def _build_structured_prompt(
        self,
        context: ContextPackage,
        rendered_prompt: str,
        snapshot: dict,
    ) -> str:
        context_payload, context_summary = build_structured_prompt_context(
            context,
            snapshot,
            include_session_state=True,
            include_wakeup_context=True,
        )
        context_json = json.dumps(context_payload, ensure_ascii=False, default=str)
        return (
            "You are producing the runtime analysis result for the host application.\n"
            "Decide whether the assistant should reply now or stay silent.\n"
            "If the current event is an idle wakeup and re-engagement feels appropriate, you may choose to reply proactively.\n"
            "Only propose wakeups that have a concrete reason.\n"
            "When editing tags, you may only use tag indexes from the allowed tag catalog shown in the context, including system tags when they are present.\n"
            "Never invent new tag names or output free-text tags.\n"
            "If the current event is a plugin or other wakeup, distill the useful wakeup details into event_summary for continuity.\n"
            "Do not assume future rounds will still receive the raw wakeup payload.\n"
            "If the current event is a wakeup and you choose silence, you must still provide a concise event_summary so future rounds do not lose the wakeup context.\n"
            "Use memory_ops to manage long-term memory carefully. importance below 3 should remain candidate-level rather than durable memory.\n"
            "Use fact_cache_ops for time-sensitive facts with TTL rather than durable user preferences.\n"
            f"{context_summary}\n"
            "CONTEXT_JSON_START\n"
            f"{context_json}\n"
            "CONTEXT_JSON_END\n"
            "PROMPT_TEXT_START\n"
            f"{rendered_prompt}\n"
            "PROMPT_TEXT_END"
        )

    def _normalize_event_summary(
        self,
        context: ContextPackage,
        *,
        decision: str,
        raw_summary: str | None,
    ) -> str | None:
        normalized = str(raw_summary or "").strip()
        if normalized:
            return normalized
        if decision != "silence" or context.runtime_event.event_type != "wakeup":
            return None
        wakeup_context = context.external_context.get("wakeup_context")
        if isinstance(wakeup_context, dict):
            for key in ("idle_summary", "summary", "reason"):
                value = str(wakeup_context.get(key) or "").strip()
                if value:
                    return value
        for key in ("summary", "reason"):
            value = str(context.runtime_event.payload.get(key) or "").strip()
            if value:
                return value
        return "Wakeup event evaluated without a visible reply."

    def _fallback_decision(self, context: ContextPackage, latest_content: str) -> MetaDecision:
        event_type = context.runtime_event.event_type
        if event_type == "wakeup":
            reason = str(context.runtime_event.payload.get("reason") or "scheduled wakeup")
            return MetaDecision(
                decision="reply",
                relation_delta=0,
                persona_patch={"last_wakeup_reason": reason[:120]},
                tag_ops=[],
                internal_thought="Fallback wakeup meta decision.",
                event_summary=reason[:240],
                next_wakeup_hints=[],
                cancel_wakeup_task_ids=[],
                generation_brief=None,
                used_memory_ids=[],
                session_update={},
                task_state_update={},
                fact_cache_ops=[],
                memory_ops=[],
                request_mode="meta_reply",
            )
        if event_type == "pull":
            return MetaDecision(
                decision="reply",
                relation_delta=0,
                persona_patch={"last_pull_source": context.runtime_event.payload.get("source_cocoon_id")},
                tag_ops=[],
                internal_thought="Fallback pull meta decision.",
                event_summary=None,
                next_wakeup_hints=[],
                cancel_wakeup_task_ids=[],
                generation_brief=None,
                used_memory_ids=[],
                session_update={},
                task_state_update={},
                fact_cache_ops=[],
                memory_ops=[],
                request_mode="meta_reply",
            )
        if event_type == "merge":
            return MetaDecision(
                decision="reply",
                relation_delta=0,
                persona_patch={"last_merge_source": context.runtime_event.payload.get("source_cocoon_id")},
                tag_ops=[],
                internal_thought="Fallback merge meta decision.",
                event_summary=None,
                next_wakeup_hints=[],
                cancel_wakeup_task_ids=[],
                generation_brief=None,
                used_memory_ids=[],
                session_update={},
                task_state_update={},
                fact_cache_ops=[],
                memory_ops=[],
                request_mode="meta_reply",
            )
        return MetaDecision(
            decision="silence" if latest_content.strip().startswith("/silent") else "reply",
            relation_delta=1 if latest_content else 0,
            persona_patch={"last_seen_intent": latest_content[:120]},
            tag_ops=[],
            internal_thought="Fallback chat meta decision.",
            event_summary=None,
            next_wakeup_hints=[],
            cancel_wakeup_task_ids=[],
            generation_brief=None,
            used_memory_ids=[],
            session_update={},
            task_state_update={},
            fact_cache_ops=[],
            memory_ops=[],
            request_mode="meta_reply",
        )

    def _normalize_tag_ops(self, *collections) -> list[TagOperation]:
        items: list[TagOperation] = []
        for collection in collections:
            for item in collection or []:
                if int(item.tag_index) <= 0:
                    continue
                items.append(TagOperation(action=item.action, tag_index=int(item.tag_index)))
        return items

    def _normalize_fact_cache_ops(self, items) -> list[FactCacheOperation]:
        normalized: list[FactCacheOperation] = []
        for item in items or []:
            cache_key = str(item.cache_key or "").strip()
            if not cache_key:
                continue
            normalized.append(
                FactCacheOperation(
                    op=item.op,
                    cache_key=cache_key,
                    content=str(item.content or ""),
                    summary=str(item.summary or "").strip() or None,
                    valid_until=str(item.valid_until or "").strip() or None,
                    meta_json=item.meta_json or {},
                )
            )
        return normalized

    def _normalize_memory_ops(self, items) -> list[MemoryOperation]:
        normalized: list[MemoryOperation] = []
        for item in items or []:
            if item.op == "none":
                continue
            tags: list[TagReference] = []
            for tag in item.tags or []:
                if isinstance(tag, str):
                    tag_value = tag.strip()
                else:
                    tag_value = str(getattr(tag, "tag", "")).strip()
                if tag_value:
                    tags.append(TagReference(tag=tag_value))
            normalized.append(
                MemoryOperation(
                    op=item.op,
                    content=str(item.content or "").strip(),
                    summary=str(item.summary or "").strip() or None,
                    memory_type=str(item.memory_type or "preference"),
                    memory_pool=str(item.memory_pool).strip() if item.memory_pool else None,
                    tags=tags,
                    importance=int(item.importance or 3),
                    confidence=int(item.confidence or 3),
                    reason=str(item.reason or "").strip() or None,
                    valid_until=str(item.valid_until or "").strip() or None,
                    target_memory_id=str(item.target_memory_id or "").strip() or None,
                    supersedes_memory_ids=[
                        str(value).strip()
                        for value in item.supersedes_memory_ids
                        if str(value).strip()
                    ],
                )
            )
        return normalized
