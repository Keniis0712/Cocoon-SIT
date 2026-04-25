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
from app.services.runtime.types import ContextPackage, MemoryCandidate, MetaDecision, TagOperation, TagReference
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
        return MetaDecision(
            decision=parsed.decision,
            relation_delta=relation_delta_int,
            persona_patch=parsed.persona_patch or {"last_seen_intent": latest_content[:120]},
            tag_ops=[
                TagOperation(action=item.action, tag=item.tag.strip())
                for item in parsed.tag_ops
                if item.tag.strip()
            ],
            internal_thought=internal_thought,
            next_wakeup_hints=self._normalize_wakeup_hints(parsed.schedule_wakeups),
            cancel_wakeup_task_ids=[str(item) for item in parsed.cancel_wakeup_task_ids if str(item).strip()],
            generation_brief=parsed.generation_brief,
            memory_candidates=[
                MemoryCandidate(
                    scope=item.scope,
                    summary=item.summary,
                    content=item.content,
                    tags=[TagReference(tag=tag.tag.strip()) for tag in item.tags if tag.tag.strip()],
                    owner_user_id=item.owner_user_id,
                    importance=item.importance,
                )
                for item in parsed.memory_candidates
                if item.summary.strip() and item.content.strip()
            ],
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
        )
        context_json = json.dumps(context_payload, ensure_ascii=False, default=str)
        return (
            "You are producing the runtime analysis result for the host application.\n"
            "Decide whether the assistant should reply now or stay silent, then extract only durable memories worth retrieving later.\n"
            "If the current event is an idle wakeup and re-engagement feels appropriate, you may choose to reply proactively.\n"
            "Only propose wakeups that have a concrete reason.\n"
            "Only extract memory candidates for durable facts, preferences, commitments, or event conclusions.\n"
            "Do not turn the assistant's draft reply or ordinary chit-chat into long-term memory.\n"
            f"{context_summary}\n"
            "CONTEXT_JSON_START\n"
            f"{context_json}\n"
            "CONTEXT_JSON_END\n"
            "PROMPT_TEXT_START\n"
            f"{rendered_prompt}\n"
            "PROMPT_TEXT_END"
        )

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
                next_wakeup_hints=[],
                cancel_wakeup_task_ids=[],
                generation_brief=None,
                memory_candidates=[],
            )
        if event_type == "pull":
            return MetaDecision(
                decision="reply",
                relation_delta=0,
                persona_patch={"last_pull_source": context.runtime_event.payload.get("source_cocoon_id")},
                tag_ops=[],
                internal_thought="Fallback pull meta decision.",
                next_wakeup_hints=[],
                cancel_wakeup_task_ids=[],
                generation_brief=None,
                memory_candidates=[],
            )
        if event_type == "merge":
            return MetaDecision(
                decision="reply",
                relation_delta=0,
                persona_patch={"last_merge_source": context.runtime_event.payload.get("source_cocoon_id")},
                tag_ops=[],
                internal_thought="Fallback merge meta decision.",
                next_wakeup_hints=[],
                cancel_wakeup_task_ids=[],
                generation_brief=None,
                memory_candidates=[],
            )
        return MetaDecision(
            decision="silence" if latest_content.strip().startswith("/silent") else "reply",
            relation_delta=1 if latest_content else 0,
            persona_patch={"last_seen_intent": latest_content[:120]},
            tag_ops=[],
            internal_thought="Fallback chat meta decision.",
            next_wakeup_hints=[],
            cancel_wakeup_task_ids=[],
            generation_brief=None,
            memory_candidates=[],
        )
