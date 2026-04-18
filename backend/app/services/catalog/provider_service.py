"""Provider registry administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelProvider
from app.schemas.catalog.providers import ModelProviderCreate


class ProviderService:
    """Creates, lists, and updates model providers."""

    def list_providers(self, session: Session) -> list[ModelProvider]:
        """Return providers ordered by creation time."""
        return list(session.scalars(select(ModelProvider).order_by(ModelProvider.created_at.asc())).all())

    def create_provider(self, session: Session, payload: ModelProviderCreate) -> ModelProvider:
        """Create a new model provider record."""
        provider = ModelProvider(
            name=payload.name,
            kind=payload.kind,
            base_url=payload.base_url,
            capabilities_json=payload.capabilities_json,
        )
        session.add(provider)
        session.flush()
        return provider

    def update_provider(self, session: Session, provider_id: str, payload: ModelProviderCreate) -> ModelProvider:
        """Update an existing provider record."""
        provider = session.get(ModelProvider, provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        provider.name = payload.name
        provider.kind = payload.kind
        provider.base_url = payload.base_url
        provider.capabilities_json = payload.capabilities_json
        session.flush()
        return provider
