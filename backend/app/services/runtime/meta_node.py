"""Runtime meta-decision service."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.services.audit.service import AuditService
from app.services.prompts.service import PromptTemplateService
from app.services.providers.base import MockChatProvider
from app.services.runtime.prompting import build_runtime_prompt_variables, record_prompt_render_artifacts
from app.services.runtime.structured_output import extract_json_object
from app.services.runtime.types import ContextPackage, MetaDecision
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
        provider_capabilities = provider_record.capabilities_json | {
            "provider_kind": provider_record.kind,
            "model_name": model.model_name,
        }
        template, revision, snapshot, rendered_prompt = self.prompt_service.render(
            session=session,
            template_type="meta",
            variables=build_runtime_prompt_variables(
                context,
                provider_capabilities=provider_capabilities,
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
        response = provider.generate_text(
            prompt=provider_prompt,
            messages=[self._provider_message_payload(message, context) for message in context.visible_messages],
            model_name=model.model_name,
            provider_config=runtime_provider_config,
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
        parsed = extract_json_object(response.text) or {}
        if not parsed:
            return self._fallback_decision(context, latest_content)
        decision = str(parsed.get("decision") or "reply")
        if decision not in {"reply", "silence"}:
            decision = "reply"
        relation_delta = parsed.get("relation_delta")
        try:
            relation_delta_int = int(relation_delta) if relation_delta is not None else (1 if latest_content else 0)
        except Exception:
            relation_delta_int = 1 if latest_content else 0
        persona_patch = parsed.get("persona_patch")
        if not isinstance(persona_patch, dict):
            persona_patch = {"last_seen_intent": latest_content[:120]}
        tag_ops = parsed.get("tag_ops")
        if not isinstance(tag_ops, list):
            tag_ops = []
        wakeups = parsed.get("schedule_wakeups")
        if not isinstance(wakeups, list):
            wakeups = []
        cancel_wakeup_task_ids = parsed.get("cancel_wakeup_task_ids")
        if not isinstance(cancel_wakeup_task_ids, list):
            cancel_wakeup_task_ids = []
        internal_thought = str(parsed.get("internal_thought") or "Structured meta decision completed.")
        return MetaDecision(
            decision=decision,
            relation_delta=relation_delta_int,
            persona_patch=persona_patch,
            tag_ops=[str(item) for item in tag_ops if str(item).strip()],
            internal_thought=internal_thought,
            next_wakeup_hints=[item for item in wakeups if isinstance(item, dict)],
            cancel_wakeup_task_ids=[str(item) for item in cancel_wakeup_task_ids if str(item).strip()],
        )

    def _build_structured_prompt(
        self,
        context: ContextPackage,
        rendered_prompt: str,
        snapshot: dict,
    ) -> str:
        context_json = json.dumps(
            {
                "runtime_event": {
                    "event_type": context.runtime_event.event_type,
                    "target_type": context.runtime_event.target_type,
                    "target_id": context.runtime_event.target_id,
                    **context.runtime_event.payload,
                },
                "session_state": snapshot.get("session_state"),
                "pending_wakeups": context.external_context.get("pending_wakeups", []),
                "wakeup_context": context.external_context.get("wakeup_context"),
                "now_utc": context.external_context.get("now_utc"),
            },
            ensure_ascii=False,
            default=str,
        )
        return (
            f"{MockChatProvider.META_MARKER}\n"
            "Return a strict JSON object with keys: decision, relation_delta, persona_patch, "
            "tag_ops, internal_thought, schedule_wakeups, cancel_wakeup_task_ids.\n"
            "Use decision='reply' when the assistant should actively answer now, decision='silence' when it should ignore this wakeup.\n"
            "When the conversation stopped and the current event is an idle wakeup, you are encouraged to proactively re-engage the user at an appropriate moment.\n"
            "schedule_wakeups must be an array. Each wakeup must include a non-empty reason and may define run_at, delay_seconds, delay_minutes, or delay_hours.\n"
            "cancel_wakeup_task_ids must contain exact ids from pending_wakeups when you want to cancel them.\n"
            "CONTEXT_JSON_START\n"
            f"{context_json}\n"
            "CONTEXT_JSON_END\n"
            "PROMPT_TEXT_START\n"
            f"{rendered_prompt}\n"
            "PROMPT_TEXT_END"
        )

    def _provider_message_payload(self, message, context: ContextPackage) -> dict[str, str]:
        content = message.content
        if context.target_type == "chat_group" and message.role == "user" and message.sender_user_id:
            content = f"[sender:{message.sender_user_id}] {content}"
        if message.is_retracted:
            content = f"{content}\n\n[system note: this message was later retracted]"
        return {"role": message.role, "content": content}

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
            )
        return MetaDecision(
            decision="silence" if latest_content.strip().startswith("/silent") else "reply",
            relation_delta=1 if latest_content else 0,
            persona_patch={"last_seen_intent": latest_content[:120]},
            tag_ops=[],
            internal_thought="Fallback chat meta decision.",
            next_wakeup_hints=[],
            cancel_wakeup_task_ids=[],
        )
