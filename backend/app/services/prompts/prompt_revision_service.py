from __future__ import annotations

import hashlib

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PromptTemplate, PromptTemplateRevision
from app.services.prompts.registry import (
    DEFAULT_TEMPLATES,
    PROMPT_VARIABLES_BY_TYPE,
    get_default_template_payload,
)
from app.services.prompts.renderer import find_placeholders


class PromptRevisionService:
    """Handles template lookup and revisioned persistence."""

    def ensure_default_templates(self, session: Session) -> None:
        for template_type in DEFAULT_TEMPLATES:
            existing = session.scalar(
                select(PromptTemplate).where(PromptTemplate.template_type == str(template_type))
            )
            if existing:
                continue
            name, description, content = get_default_template_payload(str(template_type))
            self.upsert_template(
                session=session,
                template_type=str(template_type),
                name=name,
                description=description,
                content=content,
                actor_user_id=None,
            )

    def list_templates(self, session: Session) -> list[PromptTemplate]:
        return list(session.scalars(select(PromptTemplate).order_by(PromptTemplate.template_type)).all())

    def get_template(self, session: Session, template_type: str) -> PromptTemplate:
        template = session.scalar(
            select(PromptTemplate).where(PromptTemplate.template_type == template_type)
        )
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        return template

    def get_active_revision(self, session: Session, template: PromptTemplate) -> PromptTemplateRevision | None:
        if not template.active_revision_id:
            return None
        return session.get(PromptTemplateRevision, template.active_revision_id)

    def reset_template(
        self,
        session: Session,
        template_type: str,
        actor_user_id: str | None,
    ) -> PromptTemplate:
        try:
            name, description, content = get_default_template_payload(template_type)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found") from exc

        return self.upsert_template(
            session=session,
            template_type=template_type,
            name=name,
            description=description,
            content=content,
            actor_user_id=actor_user_id,
        )

    def upsert_template(
        self,
        session: Session,
        template_type: str,
        name: str,
        description: str,
        content: str,
        actor_user_id: str | None,
    ) -> PromptTemplate:
        allowed = set(PROMPT_VARIABLES_BY_TYPE.get(template_type, {}).keys())
        placeholders = find_placeholders(content)
        unknown = sorted(set(placeholders) - allowed)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown prompt variables: {', '.join(unknown)}",
            )

        template = session.scalar(
            select(PromptTemplate).where(PromptTemplate.template_type == template_type)
        )
        if not template:
            template = PromptTemplate(
                template_type=template_type,
                name=name,
                description=description,
            )
            session.add(template)
            session.flush()
        else:
            template.name = name
            template.description = description
            session.flush()

        current_version = session.scalar(
            select(PromptTemplateRevision.version)
            .where(PromptTemplateRevision.template_id == template.id)
            .order_by(PromptTemplateRevision.version.desc())
        )
        version = (current_version or 0) + 1
        revision = PromptTemplateRevision(
            template_id=template.id,
            version=version,
            content=content,
            variables_json=placeholders,
            checksum=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            created_by_user_id=actor_user_id,
        )
        session.add(revision)
        session.flush()
        template.active_revision_id = revision.id
        session.flush()
        return template
