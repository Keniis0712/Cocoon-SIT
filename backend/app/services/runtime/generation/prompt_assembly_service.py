"""Prompt-assembly subservice for generation rounds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import PromptTemplate, PromptTemplateRevision
from app.services.prompts.service import PromptTemplateService
from app.services.runtime.prompting import build_provider_message_payload, build_runtime_prompt_variables
from app.services.runtime.types import ContextPackage


_CONTEXT_HEADINGS = ("角色专属设定：", "当前会话状态：")
_GLOBAL_RULES_HEADING = "全局规则："


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
        combined_prompt = self._combine_prompts(system_prompt, rendered_prompt)
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
            messages=[build_provider_message_payload(message, context) for message in message_source],
        )

    def _combine_prompts(self, system_prompt: str, event_prompt: str) -> str:
        system_prompt = self._trim_overlapping_system_context(system_prompt, event_prompt)
        return f"{system_prompt}\n\n{event_prompt}".strip()

    def _trim_overlapping_system_context(self, system_prompt: str, event_prompt: str) -> str:
        if not all(heading in event_prompt for heading in _CONTEXT_HEADINGS):
            return system_prompt
        if not all(heading in system_prompt for heading in _CONTEXT_HEADINGS):
            return system_prompt
        rules_index = system_prompt.find(_GLOBAL_RULES_HEADING)
        if rules_index < 0:
            return system_prompt
        context_index = min(system_prompt.find(heading) for heading in _CONTEXT_HEADINGS)
        prefix = system_prompt[:context_index].strip()
        rules = system_prompt[rules_index:].strip()
        return f"{prefix}\n\n{rules}".strip()
