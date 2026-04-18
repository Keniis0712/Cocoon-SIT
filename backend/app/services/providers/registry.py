"""Provider registry that resolves chat providers from model metadata."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AvailableModel, EmbeddingProvider, ModelProvider
from app.services.providers.base import ChatProvider, EmbeddingProvider as EmbeddingProviderAdapter
from app.services.providers.model_selection_service import ModelSelectionService
from app.services.providers.provider_factory import ProviderFactory
from app.services.providers.provider_runtime_config_service import ProviderRuntimeConfigService


class ProviderRegistry:
    """Maps model ids to concrete provider implementations and config."""

    def __init__(
        self,
        model_selection_service: ModelSelectionService,
        runtime_config_service: ProviderRuntimeConfigService,
        provider_factory: ProviderFactory,
    ) -> None:
        self.model_selection_service = model_selection_service
        self.runtime_config_service = runtime_config_service
        self.provider_factory = provider_factory

    def resolve_chat_provider(
        self, session: Session, model_id: str
    ) -> tuple[ChatProvider, AvailableModel, ModelProvider, dict]:
        model, provider = self.model_selection_service.resolve_chat_model(session, model_id)
        runtime_config = self.runtime_config_service.build_chat_config(session, provider, model)
        chat_provider = self.provider_factory.resolve_chat_provider(provider.kind)
        return chat_provider, model, provider, runtime_config

    def resolve_embedding_provider(
        self,
        session: Session,
    ) -> tuple[EmbeddingProviderAdapter, EmbeddingProvider, dict] | None:
        providers = list(
            session.scalars(
                select(EmbeddingProvider)
                .where(EmbeddingProvider.is_enabled.is_(True))
                .order_by(EmbeddingProvider.created_at.asc())
            ).all()
        )
        if not providers:
            return None
        if len(providers) > 1:
            raise ValueError("Expected exactly one active embedding provider")
        provider_record = providers[0]
        runtime_config = self.runtime_config_service.build_embedding_config(provider_record)
        provider = self.provider_factory.resolve_embedding_provider(provider_record.kind)
        return provider, provider_record, runtime_config
