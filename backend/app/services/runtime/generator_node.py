"""Runtime generation service."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.services.audit.service import AuditService
from app.services.providers.base import MockChatProvider
from app.services.providers.registry import ProviderRegistry
from app.services.runtime.generation.prompt_assembly_service import PromptAssemblyService
from app.services.runtime.prompting import record_prompt_render_artifacts
from app.services.runtime.structured_models import GenerationStructuredOutputModel
from app.services.runtime.types import ContextPackage, GenerationOutput
from app.services.runtime.types import MetaDecision


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
        provider_capabilities = provider_record.capabilities_json | {
            "provider_kind": provider_record.kind,
            "model_name": model.model_name,
        }
        assembly = self.prompt_assembly_service.build(
            session=session,
            context=context,
            provider_capabilities=provider_capabilities,
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
            prompt=self._build_structured_prompt(context, assembly.combined_prompt, meta),
            messages=assembly.messages,
            model_name=model.model_name,
            provider_config=runtime_provider_config,
            schema=GenerationStructuredOutputModel.model_json_schema(),
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

    def _build_structured_prompt(self, context: ContextPackage, rendered_prompt: str, meta: MetaDecision) -> str:
        context_json = json.dumps(
            {
                "runtime_event": {
                    "event_type": context.runtime_event.event_type,
                    "target_type": context.runtime_event.target_type,
                    "target_id": context.runtime_event.target_id,
                    **context.runtime_event.payload,
                },
                "wakeup_context": context.external_context.get("wakeup_context"),
                "pending_wakeups": context.external_context.get("pending_wakeups", []),
                "now_utc": context.external_context.get("now_utc"),
                "generation_brief": meta.generation_brief,
            },
            ensure_ascii=False,
            default=str,
        )
        return (
            f"{MockChatProvider.GENERATOR_MARKER}\n"
            "Return a strict JSON object with key reply_text.\n"
            "If this is an idle wakeup, you may proactively message the user, mention that the conversation became quiet, "
            "and use the provided time/reason context naturally.\n"
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
