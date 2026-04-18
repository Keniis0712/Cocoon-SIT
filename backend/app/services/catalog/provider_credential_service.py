"""Provider credential administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelProvider, ProviderCredential
from app.schemas.catalog.providers import ProviderCredentialCreate, ProviderCredentialOut
from app.services.security.encryption import SecretCipher


class ProviderCredentialService:
    """Creates, rotates, and reads provider credentials."""

    def __init__(self, secret_cipher: SecretCipher) -> None:
        self.secret_cipher = secret_cipher

    def set_credential(
        self,
        session: Session,
        provider_id: str,
        payload: ProviderCredentialCreate,
    ) -> ProviderCredentialOut:
        """Create or update the credential associated with a provider."""
        provider = session.get(ModelProvider, provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        credential = session.scalar(
            select(ProviderCredential).where(ProviderCredential.provider_id == provider_id)
        )
        if not credential:
            credential = ProviderCredential(
                provider_id=provider_id,
                secret_encrypted=self.secret_cipher.encrypt(payload.secret),
                metadata_json=payload.metadata_json,
            )
            session.add(credential)
        else:
            credential.secret_encrypted = self.secret_cipher.encrypt(payload.secret)
            credential.metadata_json = payload.metadata_json
        session.flush()
        result = ProviderCredentialOut.model_validate(credential)
        result.masked_secret = SecretCipher.mask_secret(payload.secret)
        return result

    def get_credential(self, session: Session, provider_id: str) -> ProviderCredentialOut:
        """Return credential metadata and a masked view of the secret."""
        credential = session.scalar(
            select(ProviderCredential).where(ProviderCredential.provider_id == provider_id)
        )
        if not credential:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider credential not found")
        secret = self.secret_cipher.decrypt(credential.secret_encrypted)
        result = ProviderCredentialOut.model_validate(credential)
        result.masked_secret = SecretCipher.mask_secret(secret)
        return result
