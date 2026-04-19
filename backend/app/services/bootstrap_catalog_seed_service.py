from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TagRegistry
from app.services.prompts.service import PromptTemplateService


class BootstrapCatalogSeedService:
    """Seeds prompt metadata and system tags required for startup."""

    def ensure_defaults(
        self,
        session: Session,
        prompt_service: PromptTemplateService,
    ) -> None:
        prompt_service.ensure_defaults(session)

        default_tag = session.scalar(select(TagRegistry).where(TagRegistry.tag_id == "default"))
        if not default_tag:
            session.add(
                TagRegistry(
                    tag_id="default",
                    brief="Default visible tag boundary for new cocoons and messages.",
                    is_isolated=False,
                    meta_json={"system": True},
                )
            )
            session.flush()
        return None
