"""Runtime generation service."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.services.audit.service import AuditService
from app.services.providers.registry import ProviderRegistry
from app.services.runtime.generation.prompt_assembly_service import PromptAssemblyService
from app.services.runtime.prompting.prompting import (
    build_structured_prompt_context,
    record_prompt_render_artifacts,
)
from app.services.runtime.structured_models import (
    GenerationStructuredOutputModel,
    ReplyOnlyStructuredOutputModel,
    ScheduledWakeupModel,
    SinglePassStructuredOutputModel,
)
from app.services.runtime.types import (
    ContextPackage,
    FactCacheOperation,
    GenerationOutput,
    MemoryOperation,
    MetaDecision,
    TagOperation,
    TagReference,
)


class GeneratorNode:
    """Streams model output after prompts and provider configuration are resolved."""

    def __init__(
        self,
        prompt_assembly_service: PromptAssemblyService,
        provider_registry: ProviderRegistry,
        audit_service: AuditService,
    ) -> None:
        self.prompt_assembly_service = prompt_assembly_service
        self.provider_registry = provider_registry
        self.audit_service = audit_service

    def generate(
        self,
        session: Session,
        context: ContextPackage,
        meta: MetaDecision,
        audit_run,
        audit_step,
    ) -> GenerationOutput:
        provider, model, provider_record, runtime_provider_config = self.provider_registry.resolve_chat_provider(
            session, context.cocoon.selected_model_id
        )
        assembly = self.prompt_assembly_service.build(
            session=session,
            context=context,
            provider_capabilities=provider_record.capabilities_json,
        )
        for segment in (assembly.system, assembly.event):
            record_prompt_render_artifacts(
                session,
                self.audit_service,
                audit_run,
                audit_step,
                segment.template,
                segment.revision,
                segment.snapshot,
                segment.rendered_prompt,
                summary_prefix=segment.summary_prefix,
            )
        response = provider.generate_structured(
            prompt=self._build_structured_prompt(
                context,
                assembly.combined_prompt,
                meta,
                prompt_snapshot=assembly.event.snapshot,
            ),
            messages=assembly.messages,
            model_name=model.model_name,
            provider_config=runtime_provider_config,
            schema_model=GenerationStructuredOutputModel,
            output_name="cocoon_generation_output",
        )
        parsed = GenerationStructuredOutputModel.model_validate(response.parsed or {"reply_text": response.text.strip()})
        reply_text = parsed.reply_text.strip() or response.text.strip()
        self.audit_service.record_json_artifact(
            session,
            audit_run,
            audit_step,
            "provider_raw_output",
            response.raw_response,
            summary="Provider raw generation output",
            metadata_json={
                "provider_kind": provider_record.kind,
                "model_name": model.model_name,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )
        return GenerationOutput(
            rendered_prompt=assembly.combined_prompt,
            chunks=self._build_chunks(reply_text),
            reply_text=reply_text,
            raw_response=response.raw_response,
            structured_output={"reply_text": reply_text},
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            provider_kind=provider_record.kind,
            model_name=model.model_name,
        )

    def generate_inline(
        self,
        session: Session,
        context: ContextPackage,
        audit_run,
        audit_step,
        *,
        mode: str,
    ) -> tuple[MetaDecision, GenerationOutput | None]:
        provider, model, provider_record, runtime_provider_config = self.provider_registry.resolve_chat_provider(
            session, context.cocoon.selected_model_id
        )
        assembly = self.prompt_assembly_service.build(
            session=session,
            context=context,
            provider_capabilities=provider_record.capabilities_json,
        )
        for segment in (assembly.system, assembly.event):
            record_prompt_render_artifacts(
                session,
                self.audit_service,
                audit_run,
                audit_step,
                segment.template,
                segment.revision,
                segment.snapshot,
                segment.rendered_prompt,
                summary_prefix=segment.summary_prefix,
            )
        if mode == "reply_only":
            schema_model = ReplyOnlyStructuredOutputModel
        else:
            schema_model = SinglePassStructuredOutputModel
        response = provider.generate_structured(
            prompt=self._build_inline_structured_prompt(
                context,
                assembly.combined_prompt,
                mode=mode,
                prompt_snapshot=assembly.event.snapshot,
            ),
            messages=assembly.messages,
            model_name=model.model_name,
            provider_config=runtime_provider_config,
            schema_model=schema_model,
            output_name=f"cocoon_{mode}_output",
        )
        self.audit_service.record_json_artifact(
            session,
            audit_run,
            audit_step,
            "provider_raw_output",
            response.raw_response,
            summary="Provider raw inline output",
            metadata_json={
                "provider_kind": provider_record.kind,
                "model_name": model.model_name,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "request_mode": mode,
            },
        )
        if mode == "reply_only":
            parsed = ReplyOnlyStructuredOutputModel.model_validate(
                response.parsed or {"reply_text": response.text.strip(), "internal_thought": ""}
            )
            reply_text = parsed.reply_text.strip() or response.text.strip()
            meta = MetaDecision(
                decision="reply" if reply_text else "silence",
                relation_delta=0,
                persona_patch={},
                tag_ops=[],
                internal_thought=str(parsed.internal_thought or "").strip() or "Inline reply generated.",
                event_summary=None,
                next_wakeup_hints=[],
                cancel_wakeup_task_ids=[],
                generation_brief=None,
                used_memory_ids=[],
                session_update={},
                task_state_update={},
                fact_cache_ops=[],
                memory_ops=[],
                request_mode=mode,
            )
            generation = GenerationOutput(
                rendered_prompt=assembly.combined_prompt,
                chunks=self._build_chunks(reply_text),
                reply_text=reply_text,
                raw_response=response.raw_response,
                structured_output={"reply_text": reply_text, "internal_thought": meta.internal_thought},
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                provider_kind=provider_record.kind,
                model_name=model.model_name,
                internal_thought=meta.internal_thought,
            )
            return meta, generation

        parsed = SinglePassStructuredOutputModel.model_validate(
            response.parsed
            or {
                "reply_text": response.text.strip(),
                "internal_thought": "",
                "decision": "reply",
            }
        )
        reply_text = parsed.reply_text.strip() or response.text.strip()
        meta = MetaDecision(
            decision=parsed.decision,
            relation_delta=int(parsed.session_update.relation_delta or 0),
            persona_patch=dict(parsed.session_update.persona_patch or {}),
            tag_ops=[
                TagOperation(action=item.action, tag_index=int(item.tag_index))
                for item in parsed.session_update.tag_ops
                if int(item.tag_index) > 0
            ],
            internal_thought=str(parsed.internal_thought or "").strip() or "Inline response generated.",
            event_summary=str(parsed.event_summary or "").strip() or None,
            next_wakeup_hints=self._normalize_wakeup_hints(parsed.schedule_wakeups),
            cancel_wakeup_task_ids=[str(item) for item in parsed.cancel_wakeup_task_ids if str(item).strip()],
            generation_brief=parsed.generation_brief,
            used_memory_ids=[str(item) for item in parsed.used_memory_ids if str(item).strip()],
            session_update=parsed.session_update.model_dump(exclude_none=True),
            task_state_update=parsed.task_state_update.model_dump(exclude_none=True),
            fact_cache_ops=[
                FactCacheOperation(
                    op=item.op,
                    cache_key=str(item.cache_key),
                    content=str(item.content or ""),
                    summary=str(item.summary or "").strip() or None,
                    valid_until=str(item.valid_until or "").strip() or None,
                    meta_json=item.meta_json or {},
                )
                for item in parsed.fact_cache_ops
                if str(item.cache_key or "").strip()
            ],
            memory_ops=[
                MemoryOperation(
                    op=item.op,
                    content=str(item.content or "").strip(),
                    summary=str(item.summary or "").strip() or None,
                    memory_type=str(item.memory_type or "preference"),
                    memory_pool=str(item.memory_pool).strip() if item.memory_pool else None,
                    tags=[
                        TagReference(tag=(tag if isinstance(tag, str) else str(getattr(tag, "tag", ""))).strip())
                        for tag in item.tags or []
                        if (tag if isinstance(tag, str) else str(getattr(tag, "tag", ""))).strip()
                    ],
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
                for item in parsed.memory_ops
                if item.op != "none"
            ],
            request_mode=mode,
        )
        generation = GenerationOutput(
            rendered_prompt=assembly.combined_prompt,
            chunks=self._build_chunks(reply_text),
            reply_text=reply_text,
            raw_response=response.raw_response,
            structured_output={
                "reply_text": reply_text,
                "internal_thought": meta.internal_thought,
                "decision": meta.decision,
            },
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            provider_kind=provider_record.kind,
            model_name=model.model_name,
            internal_thought=meta.internal_thought,
        )
        return meta, generation

    def _build_structured_prompt(
        self,
        context: ContextPackage,
        rendered_prompt: str,
        meta: MetaDecision,
        *,
        prompt_snapshot: dict,
    ) -> str:
        context_payload, context_summary = build_structured_prompt_context(
            context,
            prompt_snapshot,
            generation_brief=meta.generation_brief,
            include_wakeup_context=True,
        )
        context_json = json.dumps(context_payload, ensure_ascii=False, default=str)
        generation_guidance = ""
        if meta.generation_brief:
            generation_guidance = (
                "\nMETA_DECISION_GUIDANCE_START\n"
                "Use this brief as the primary generation focus from the previous runtime decision. "
                "Do not quote it or expose that it exists.\n"
                f"{meta.generation_brief}\n"
                "META_DECISION_GUIDANCE_END\n"
            )
        return (
            "You are producing the assistant's visible reply for the host application.\n"
            "If this is an idle wakeup, you may proactively re-engage the user and naturally weave in the time or reason context.\n"
            "Stay in character and focus on the most relevant continuity from the current conversation.\n"
            f"{context_summary}\n"
            "CONTEXT_JSON_START\n"
            f"{context_json}\n"
            "CONTEXT_JSON_END\n"
            f"{generation_guidance}"
            "PROMPT_TEXT_START\n"
            f"{rendered_prompt}\n"
            "PROMPT_TEXT_END"
        )

    def _build_inline_structured_prompt(
        self,
        context: ContextPackage,
        rendered_prompt: str,
        *,
        mode: str,
        prompt_snapshot: dict,
    ) -> str:
        context_payload, context_summary = build_structured_prompt_context(
            context,
            prompt_snapshot,
            include_wakeup_context=True,
        )
        context_json = json.dumps(context_payload, ensure_ascii=False, default=str)
        if mode == "reply_only":
            instructions = (
                "You are producing a fast chat reply for the host application.\n"
                "Return only the visible reply and a concise internal_thought.\n"
                "Do not create or modify memory in this mode.\n"
            )
        else:
            instructions = (
                "You are producing a visible reply and the memory/state operations for the host application.\n"
                "Use fact_cache_ops for time-sensitive facts, memory_ops for durable or candidate memories, and task_state_update for active task progress.\n"
                "Only persist durable memory when importance is at least 3.\n"
            )
        return (
            f"{instructions}"
            f"{context_summary}\n"
            "CONTEXT_JSON_START\n"
            f"{context_json}\n"
            "CONTEXT_JSON_END\n"
            "PROMPT_TEXT_START\n"
            f"{rendered_prompt}\n"
            "PROMPT_TEXT_END"
        )

    def _build_chunks(self, reply_text: str) -> list[str]:
        if not reply_text:
            return []
        return [token + " " for token in reply_text.split(" ") if token]

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
