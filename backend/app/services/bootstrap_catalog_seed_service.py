from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.prompts.service import PromptTemplateService
from app.services.catalog.tag_policy import ensure_default_tag, reconcile_tag_storage


class BootstrapCatalogSeedService:
    """Seeds prompt metadata and system tags required for startup."""

    def ensure_defaults(
        self,
        session: Session,
        prompt_service: PromptTemplateService,
    ) -> None:
        prompt_service.ensure_defaults(session)
        ensure_default_tag(session)
        reconcile_tag_storage(session)
        return None
