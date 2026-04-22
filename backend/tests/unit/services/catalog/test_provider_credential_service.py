import pytest
from fastapi import HTTPException

from app.models import ModelProvider
from app.schemas.catalog.providers import ProviderCredentialCreate
from app.services.catalog.provider_credential_service import ProviderCredentialService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


class _Cipher:
    def encrypt(self, value: str) -> str:
        return f"enc:{value}"

    def decrypt(self, value: str) -> str:
        assert value.startswith("enc:")
        return value.removeprefix("enc:")


def test_provider_credential_service_sets_updates_and_reads_credentials():
    session_factory = _session_factory()
    service = ProviderCredentialService(secret_cipher=_Cipher())

    with session_factory() as session:
        provider = ModelProvider(name="provider-a", kind="mock", capabilities_json={})
        session.add(provider)
        session.commit()

        created = service.set_credential(
            session,
            provider.id,
            ProviderCredentialCreate(secret="first-secret", metadata_json={"scope": "initial"}),
        )
        updated = service.set_credential(
            session,
            provider.id,
            ProviderCredentialCreate(secret="second-secret", metadata_json={"scope": "updated"}),
        )
        fetched = service.get_credential(session, provider.id)

        assert created.provider_id == provider.id
        assert created.masked_secret
        assert updated.id == created.id
        assert updated.metadata_json == {"scope": "updated"}
        assert fetched.metadata_json == {"scope": "updated"}
        assert fetched.masked_secret.endswith("cret")


def test_provider_credential_service_validates_missing_records():
    session_factory = _session_factory()
    service = ProviderCredentialService(secret_cipher=_Cipher())

    with session_factory() as session:
        with pytest.raises(HTTPException) as missing_provider:
            service.set_credential(
                session,
                "missing",
                ProviderCredentialCreate(secret="secret", metadata_json={}),
            )
        assert missing_provider.value.status_code == 404

        with pytest.raises(HTTPException) as missing_credential:
            service.get_credential(session, "missing")
        assert missing_credential.value.status_code == 404
