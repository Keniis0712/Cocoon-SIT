"""Prompt-template admin view service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import PromptTemplateRevision, User
from app.schemas.catalog.prompts import (
    PromptTemplateDetail,
    PromptTemplateOut,
    PromptTemplateRevisionOut,
    PromptTemplateUpsertRequest,
)
from app.services.prompts.service import PromptTemplateService


class PromptTemplateAdminService:
    """Adapts prompt-template service calls into API-facing admin responses."""

    def __init__(self, prompt_service: PromptTemplateService) -> None:
        self.prompt_service = prompt_service

    def list_templates(self, session: Session) -> list[PromptTemplateDetail]:
        """Return templates with their active revisions embedded."""
        items = []
        for template in self.prompt_service.list_templates(session):
            active = (
                session.get(PromptTemplateRevision, template.active_revision_id)
                if template.active_revision_id
                else None
            )
            template_data = PromptTemplateOut.model_validate(template).model_dump()
            items.append(
                PromptTemplateDetail(
                    **template_data,
                    active_revision=(
                        PromptTemplateRevisionOut.model_validate(active) if active else None
                    ),
                )
            )
        return items

    def upsert_template(
        self,
        session: Session,
        template_type: str,
        payload: PromptTemplateUpsertRequest,
        user: User,
    ) -> PromptTemplateOut:
        """Create or update a template and return its public view."""
        template = self.prompt_service.upsert_template(
            session=session,
            template_type=template_type,
            name=payload.name,
            description=payload.description,
            content=payload.content,
            actor_user_id=user.id,
        )
        return PromptTemplateOut.model_validate(template)
