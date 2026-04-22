import pytest
from fastapi import HTTPException

from app.models import EmbeddingProvider
from app.schemas.catalog.embedding_providers import EmbeddingProviderCreate, EmbeddingProviderUpdate
from app.services.catalog.embedding_provider_service import EmbeddingProviderService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_embedding_provider_service_create_update_list_and_disable_previous_active_provider():
    session_factory = _session_factory()
    service = EmbeddingProviderService(secret_cipher=type("_Cipher", (), {"encrypt": lambda self, value: f"enc:{value}"})())

    with session_factory() as session:
        first = service.create_embedding_provider(
            session,
            EmbeddingProviderCreate(
                name="embed-a",
                provider_id="provider-1",
                model_name="model-a",
                api_key="secret-a",
                is_enabled=True,
            ),
        )
        second = service.create_embedding_provider(
            session,
            EmbeddingProviderCreate(
                name="embed-b",
                provider_id="provider-2",
                model_name="model-b",
                api_key=None,
                is_enabled=True,
            ),
        )

        assert [item.id for item in service.list_embedding_providers(session)] == [first.id, second.id]
        assert session.get(EmbeddingProvider, first.id).is_enabled is False
        assert second.secret_encrypted is None

        updated = service.update_embedding_provider(
            session,
            first.id,
            EmbeddingProviderUpdate(
                name="embed-a-updated",
                kind="openai_compatible",
                provider_id="provider-3",
                model_name="model-c",
                config_json={"dims": 8},
                api_key="secret-b",
                is_enabled=True,
            ),
        )

        assert updated.name == "embed-a-updated"
        assert updated.kind == "openai_compatible"
        assert updated.provider_id == "provider-3"
        assert updated.model_name == "model-c"
        assert updated.config_json == {"dims": 8}
        assert updated.secret_encrypted == "enc:secret-b"
        assert updated.is_enabled is True
        assert session.get(EmbeddingProvider, second.id).is_enabled is False

        cleared = service.update_embedding_provider(
            session,
            first.id,
            EmbeddingProviderUpdate(api_key="", is_enabled=False),
        )
        assert cleared.secret_encrypted is None
        assert cleared.is_enabled is False


def test_embedding_provider_service_rejects_missing_provider():
    session_factory = _session_factory()
    service = EmbeddingProviderService(secret_cipher=type("_Cipher", (), {"encrypt": lambda self, value: value})())

    with session_factory() as session:
        with pytest.raises(HTTPException) as missing:
            service.update_embedding_provider(session, "missing", EmbeddingProviderUpdate(name="x"))
        assert missing.value.status_code == 404
