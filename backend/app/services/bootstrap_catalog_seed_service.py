from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AvailableModel, ModelProvider, TagRegistry
from app.services.prompts.service import PromptTemplateService


class BootstrapCatalogSeedService:
    """Seeds prompt metadata, providers, models, and tags."""

    def ensure_defaults(
        self,
        session: Session,
        prompt_service: PromptTemplateService,
        *,
        admin_user_id: str,
    ) -> AvailableModel:
        prompt_service.ensure_defaults(session)

        provider = session.scalar(select(ModelProvider).where(ModelProvider.name == "builtin-mock"))
        if not provider:
            provider = ModelProvider(
                name="builtin-mock",
                kind="mock",
                capabilities_json={"streaming": True, "provider": "builtin-mock"},
            )
            session.add(provider)
            session.flush()

        model = session.scalar(select(AvailableModel).where(AvailableModel.model_name == "mock-gpt-echo"))
        if not model:
            model = AvailableModel(
                provider_id=provider.id,
                model_name="mock-gpt-echo",
                model_kind="chat",
                is_default=True,
                config_json={"reply_prefix": "Echo"},
            )
            session.add(model)
            session.flush()

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

        return model
