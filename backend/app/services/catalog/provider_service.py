"""Provider registry administration service."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AvailableModel, Cocoon, EmbeddingProvider, ModelProvider, ProviderCredential
from app.schemas.catalog.providers import ModelProviderCreate, ProviderTestOut
from app.services.providers.provider_factory import ProviderFactory
from app.services.providers.provider_runtime_config_service import ProviderRuntimeConfigService


class ProviderService:
    """Creates, lists, updates, deletes, syncs, and tests model providers."""

    def __init__(
        self,
        provider_runtime_config_service: ProviderRuntimeConfigService,
        provider_factory: ProviderFactory,
    ) -> None:
        self.provider_runtime_config_service = provider_runtime_config_service
        self.provider_factory = provider_factory

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

    def delete_provider(self, session: Session, provider_id: str) -> ModelProvider:
        """Delete a provider when no active records still reference it."""
        provider = session.get(ModelProvider, provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        model_ids = list(
            session.scalars(select(AvailableModel.id).where(AvailableModel.provider_id == provider_id)).all()
        )
        if model_ids:
            in_use = session.scalar(
                select(Cocoon.id).where(
                    (Cocoon.selected_model_id.in_(model_ids)) | (Cocoon.summary_model_id.in_(model_ids))
                ).limit(1)
            )
            if in_use:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Provider is still referenced by existing cocoons",
                )

        linked_embedding_provider = session.scalar(
            select(EmbeddingProvider.id).where(EmbeddingProvider.provider_id == provider_id).limit(1)
        )
        if linked_embedding_provider:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Provider is still referenced by an embedding provider",
            )

        session.query(ProviderCredential).filter(ProviderCredential.provider_id == provider_id).delete()
        session.query(AvailableModel).filter(AvailableModel.provider_id == provider_id).delete()
        session.delete(provider)
        session.flush()
        return provider

    def sync_provider_models(self, session: Session, provider_id: str) -> list[AvailableModel]:
        """Fetch models from a provider and upsert them into the local catalog."""
        provider = session.get(ModelProvider, provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        model_names = self._list_remote_models(session, provider)
        existing = {
            item.model_name: item
            for item in session.scalars(
                select(AvailableModel).where(AvailableModel.provider_id == provider_id)
            ).all()
        }
        synced: list[AvailableModel] = []
        for model_name in model_names:
            model = existing.get(model_name)
            if model is None:
                model = AvailableModel(
                    provider_id=provider_id,
                    model_name=model_name,
                    model_kind="chat",
                    is_default=False,
                    config_json={},
                )
                session.add(model)
            synced.append(model)
        session.flush()
        return list(
            session.scalars(select(AvailableModel).where(AvailableModel.provider_id == provider_id).order_by(AvailableModel.created_at.asc())).all()
        )

    def test_provider(
        self,
        session: Session,
        provider_id: str,
        *,
        selected_model_id: str,
        prompt: str,
    ) -> ProviderTestOut:
        """Run a single non-streaming provider test call against a selected model."""
        provider = session.get(ModelProvider, provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        model = session.get(AvailableModel, selected_model_id)
        if not model or model.provider_id != provider_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found for provider")

        runtime_config = self.provider_runtime_config_service.build_chat_config(session, provider, model)
        chat_provider = self.provider_factory.resolve_chat_provider(provider.kind)
        response = chat_provider.generate_text(
            prompt="You are a provider connectivity test. Reply briefly.",
            messages=[{"role": "user", "content": prompt}],
            model_name=model.model_name,
            provider_config=runtime_config,
        )
        return ProviderTestOut(
            provider_id=provider.id,
            selected_model_id=model.id,
            model_name=model.model_name,
            reply=response.text,
            usage=response.usage,
            raw_response=response.raw_response,
        )

    def _list_remote_models(self, session: Session, provider: ModelProvider) -> list[str]:
        if provider.kind != "openai_compatible":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model sync is not supported for provider kind: {provider.kind}",
            )
        credential = session.scalar(
            select(ProviderCredential).where(ProviderCredential.provider_id == provider.id)
        )
        if not provider.base_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider base_url is required")
        if not credential:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider credential not found")
        secret = self.provider_runtime_config_service.secret_cipher.decrypt(credential.secret_encrypted)
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{provider.base_url.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {secret}"},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to sync provider models: {exc}",
            ) from exc

        items = payload.get("data", []) if isinstance(payload, dict) else []
        model_names: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id:
                model_names.append(model_id)
        if not model_names:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Provider returned no models",
            )
        return sorted(set(model_names))
