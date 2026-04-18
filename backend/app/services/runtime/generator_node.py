"""Runtime generation service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.audit.service import AuditService
from app.services.providers.registry import ProviderRegistry
from app.services.runtime.generation.prompt_assembly_service import PromptAssemblyService
from app.services.runtime.prompting import record_prompt_render_artifacts
from app.services.runtime.types import ContextPackage, GenerationOutput


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
        response = provider.generate_text(
            prompt=assembly.combined_prompt,
            messages=assembly.messages,
            model_name=model.model_name,
            provider_config=runtime_provider_config,
        )
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
            chunks=response.chunks,
            full_text=response.text,
            raw_response=response.raw_response,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            provider_kind=provider_record.kind,
            model_name=model.model_name,
        )
