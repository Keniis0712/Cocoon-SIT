from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import PromptTemplate, PromptTemplateRevision
from app.services.prompts.prompt_revision_service import PromptRevisionService
from app.services.prompts.renderer import render_template, sanitize_snapshot


class PromptRenderService:
    """Renders active prompt-template revisions with sanitized snapshots."""

    def __init__(self, prompt_revision_service: PromptRevisionService) -> None:
        self.prompt_revision_service = prompt_revision_service

    def render(
        self,
        session: Session,
        template_type: str,
        variables: dict[str, Any],
    ) -> tuple[PromptTemplate, PromptTemplateRevision, dict[str, Any], str]:
        template = self.prompt_revision_service.get_template(session, template_type)
        revision = self.prompt_revision_service.get_active_revision(session, template)
        if not revision:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No active revision")
        missing = [key for key in revision.variables_json if key not in variables]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Missing prompt variables: {', '.join(missing)}",
            )
        snapshot = sanitize_snapshot(variables)
        rendered = render_template(revision.content, snapshot)
        return template, revision, snapshot, rendered
