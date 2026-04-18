"""Embedding-provider catalog administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmbeddingProvider
from app.schemas.catalog.embedding_providers import EmbeddingProviderCreate, EmbeddingProviderUpdate
from app.services.security.encryption import SecretCipher


class EmbeddingProviderService:
    """Creates, lists, and updates embedding provider definitions."""

    def __init__(self, secret_cipher: SecretCipher) -> None:
        self.secret_cipher = secret_cipher

    def list_embedding_providers(self, session: Session) -> list[EmbeddingProvider]:
        """Return embedding providers ordered by creation time."""
        return list(
            session.scalars(select(EmbeddingProvider).order_by(EmbeddingProvider.created_at.asc())).all()
        )

    def _disable_other_active_providers(self, session: Session, active_provider_id: str | None) -> None:
        for item in session.scalars(
            select(EmbeddingProvider).where(EmbeddingProvider.is_enabled.is_(True))
        ).all():
            if item.id == active_provider_id:
                continue
            item.is_enabled = False

    def create_embedding_provider(
        self,
        session: Session,
        payload: EmbeddingProviderCreate,
    ) -> EmbeddingProvider:
        """Create an embedding provider definition."""
        item = EmbeddingProvider(
            name=payload.name,
            kind=payload.kind,
            provider_id=payload.provider_id,
            model_name=payload.model_name,
            config_json=payload.config_json,
            secret_encrypted=(
                self.secret_cipher.encrypt(payload.api_key)
                if payload.api_key
                else None
            ),
            is_enabled=payload.is_enabled,
        )
        session.add(item)
        session.flush()
        if item.is_enabled:
            self._disable_other_active_providers(session, item.id)
        return item

    def update_embedding_provider(
        self,
        session: Session,
        embedding_provider_id: str,
        payload: EmbeddingProviderUpdate,
    ) -> EmbeddingProvider:
        """Patch an embedding provider definition."""
        item = session.get(EmbeddingProvider, embedding_provider_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Embedding provider not found")
        if payload.name is not None:
            item.name = payload.name
        if payload.kind is not None:
            item.kind = payload.kind
        if payload.provider_id is not None:
            item.provider_id = payload.provider_id
        if payload.model_name is not None:
            item.model_name = payload.model_name
        if payload.config_json is not None:
            item.config_json = payload.config_json
        if payload.api_key is not None:
            item.secret_encrypted = (
                self.secret_cipher.encrypt(payload.api_key)
                if payload.api_key
                else None
            )
        if payload.is_enabled is not None:
            item.is_enabled = payload.is_enabled
        session.flush()
        if item.is_enabled:
            self._disable_other_active_providers(session, item.id)
        return item
