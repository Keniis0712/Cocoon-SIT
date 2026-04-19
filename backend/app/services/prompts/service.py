"""Prompt template service facade."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import PromptTemplate, PromptTemplateRevision
from app.services.prompts.prompt_render_service import PromptRenderService
from app.services.prompts.prompt_revision_service import PromptRevisionService
from app.services.prompts.prompt_variable_service import PromptVariableService


class PromptTemplateService:
    """Manages prompt templates, their revisions, and runtime rendering."""

    def __init__(
        self,
        prompt_variable_service: PromptVariableService | None = None,
        prompt_revision_service: PromptRevisionService | None = None,
        prompt_render_service: PromptRenderService | None = None,
    ) -> None:
        self.prompt_variable_service = prompt_variable_service or PromptVariableService()
        self.prompt_revision_service = prompt_revision_service or PromptRevisionService()
        self.prompt_render_service = prompt_render_service or PromptRenderService(
            self.prompt_revision_service
        )

    def ensure_defaults(self, session: Session) -> None:
        self.prompt_variable_service.sync_registry_defaults(session)
        self.prompt_revision_service.ensure_default_templates(session)

    def list_templates(self, session: Session) -> list[PromptTemplate]:
        return self.prompt_revision_service.list_templates(session)

    def get_template(self, session: Session, template_type: str) -> PromptTemplate:
        return self.prompt_revision_service.get_template(session, template_type)

    def get_active_revision(self, session: Session, template: PromptTemplate) -> PromptTemplateRevision | None:
        return self.prompt_revision_service.get_active_revision(session, template)

    def upsert_template(
        self,
        session: Session,
        template_type: str,
        name: str,
        description: str,
        content: str,
        actor_user_id: str | None,
    ) -> PromptTemplate:
        return self.prompt_revision_service.upsert_template(
            session=session,
            template_type=template_type,
            name=name,
            description=description,
            content=content,
            actor_user_id=actor_user_id,
        )

    def reset_template(
        self,
        session: Session,
        template_type: str,
        actor_user_id: str | None,
    ) -> PromptTemplate:
        return self.prompt_revision_service.reset_template(
            session=session,
            template_type=template_type,
            actor_user_id=actor_user_id,
        )

    def render(
        self,
        session: Session,
        template_type: str,
        variables: dict[str, Any],
    ) -> tuple[PromptTemplate, PromptTemplateRevision, dict[str, Any], str]:
        return self.prompt_render_service.render(session, template_type, variables)
