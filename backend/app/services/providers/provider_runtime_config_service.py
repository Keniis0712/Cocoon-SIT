"""Provider runtime configuration assembly."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AvailableModel, EmbeddingProvider, ModelProvider, ProviderCredential
from app.services.security.encryption import SecretCipher


class ProviderRuntimeConfigService:
    """Builds the runtime configuration passed into concrete chat providers."""

    def __init__(self, secret_cipher: SecretCipher) -> None:
        self.secret_cipher = secret_cipher

    def build_chat_config(
        self,
        session: Session,
        provider: ModelProvider,
        model: AvailableModel,
    ) -> dict:
        """Merge model config, provider metadata, and decrypted credentials."""
        runtime_config = dict(model.config_json)
        runtime_config["base_url"] = provider.base_url
        credential = session.scalar(
            select(ProviderCredential).where(ProviderCredential.provider_id == provider.id)
        )
        if credential:
            runtime_config["api_key"] = self.secret_cipher.decrypt(credential.secret_encrypted)
        return runtime_config

    def build_embedding_config(
        self,
        embedding_provider: EmbeddingProvider,
    ) -> dict:
        """Merge persisted embedding config with decrypted secrets."""
        runtime_config = dict(embedding_provider.config_json)
        if embedding_provider.secret_encrypted:
            runtime_config["api_key"] = self.secret_cipher.decrypt(embedding_provider.secret_encrypted)
        return runtime_config
