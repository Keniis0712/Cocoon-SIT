"""Prompt-assembly subservice for generation rounds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import PromptTemplate, PromptTemplateRevision
from app.services.prompts.service import PromptTemplateService
from app.services.runtime.prompting import build_runtime_prompt_variables
from app.services.runtime.types import ContextPackage


@dataclass
class RenderedPromptSegment:
    """A single rendered prompt segment with the metadata needed for audit."""

    template: PromptTemplate
    revision: PromptTemplateRevision
    snapshot: dict[str, Any]
    rendered_prompt: str
    summary_prefix: str


@dataclass
class PromptAssembly:
    """The fully assembled prompt package used by the generator."""

    system: RenderedPromptSegment
    event: RenderedPromptSegment
    combined_prompt: str
    messages: list[dict[str, str]]


class PromptAssemblyService:
    """Builds the system prompt, event prompt, and message payload for generation."""

    def __init__(self, prompt_service: PromptTemplateService) -> None:
        self.prompt_service = prompt_service

    def build(
        self,
        session: Session,
        context: ContextPackage,
        provider_capabilities: dict[str, Any],
    ) -> PromptAssembly:
        """Render the prompt stack and choose the message source for the provider call."""
        variables = build_runtime_prompt_variables(
            context,
            provider_capabilities=provider_capabilities,
        )
        system_template, system_revision, system_snapshot, system_prompt = self.prompt_service.render(
            session=session,
            template_type="system",
            variables=variables,
        )

        template_type = "generator"
        message_source = context.external_context.get("source_messages", context.visible_messages)
        if context.runtime_event.event_type == "pull":
            template_type = "pull"
            variables["memory_context"] = [
                {"scope": memory.scope, "summary": memory.summary, "content": memory.content}
                for memory in context.external_context.get("source_memories", context.memory_context)
            ]
        elif context.runtime_event.event_type == "merge":
            template_type = "merge"
            variables["merge_context"] = context.external_context.get("merge_context", {})

        template, revision, snapshot, rendered_prompt = self.prompt_service.render(
            session=session,
            template_type=template_type,
            variables=variables,
        )
        combined_prompt = f"{system_prompt}\n\n{rendered_prompt}".strip()
        return PromptAssembly(
            system=RenderedPromptSegment(
                template=system_template,
                revision=system_revision,
                snapshot=system_snapshot,
                rendered_prompt=system_prompt,
                summary_prefix="system",
            ),
            event=RenderedPromptSegment(
                template=template,
                revision=revision,
                snapshot=snapshot,
                rendered_prompt=rendered_prompt,
                summary_prefix=template_type,
            ),
            combined_prompt=combined_prompt,
            messages=[
                {"role": message.role, "content": message.content}
                for message in message_source
            ],
        )
