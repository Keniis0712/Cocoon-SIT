from sqlalchemy import select
import pytest

from app.models import AvailableModel, EmbeddingProvider, ModelProvider
from app.schemas.catalog.embedding_providers import EmbeddingProviderCreate, EmbeddingProviderUpdate
from app.schemas.catalog.models import AvailableModelCreate, AvailableModelUpdate
from app.schemas.catalog.providers import ModelProviderCreate, ProviderCredentialCreate

pytestmark = pytest.mark.integration


def test_provider_service_crud(client):
    container = client.app.state.container
    with container.session_factory() as session:
        created = container.provider_service.create_provider(
            session,
            ModelProviderCreate(name="svc-provider", kind="mock", base_url=None, capabilities_json={"streaming": True}),
        )
        session.commit()
        provider_id = created.id

    with container.session_factory() as session:
        updated = container.provider_service.update_provider(
            session,
            provider_id,
            ModelProviderCreate(name="svc-provider-2", kind="mock", base_url=None, capabilities_json={"streaming": False}),
        )
        providers = container.provider_service.list_providers(session)
        assert updated.name == "svc-provider-2"
        assert any(provider.id == provider_id for provider in providers)


def test_provider_credential_service_sets_and_reads_masked_secret(client):
    container = client.app.state.container
    with container.session_factory() as session:
        provider = session.scalars(select(ModelProvider)).first()
        result = container.provider_credential_service.set_credential(
            session,
            provider.id,
            ProviderCredentialCreate(secret="secret-value-1234", metadata_json={"env": "test"}),
        )
        session.commit()
        assert "*" in result.masked_secret

    with container.session_factory() as session:
        provider = session.scalars(select(ModelProvider)).first()
        fetched = container.provider_credential_service.get_credential(session, provider.id)
        assert fetched.provider_id == provider.id
        assert "*" in fetched.masked_secret


def test_model_and_embedding_catalog_services(client):
    container = client.app.state.container
    with container.session_factory() as session:
        provider = session.scalars(select(ModelProvider)).first()
        model = container.model_catalog_service.create_model(
            session,
            AvailableModelCreate(
                provider_id=provider.id,
                model_name="svc-model",
                model_kind="chat",
                is_default=False,
                config_json={"reply_prefix": "svc"},
            ),
        )
        embedding = container.embedding_provider_service.create_embedding_provider(
            session,
            EmbeddingProviderCreate(
                name="svc-embedding",
                provider_id=provider.id,
                model_name="embed-1",
                config_json={"dims": 8},
                is_enabled=True,
            ),
        )
        session.commit()

    with container.session_factory() as session:
        updated_model = container.model_catalog_service.update_model(
            session,
            model.id,
            AvailableModelUpdate(model_name="svc-model-2", is_default=True),
        )
        updated_embedding = container.embedding_provider_service.update_embedding_provider(
            session,
            embedding.id,
            EmbeddingProviderUpdate(name="svc-embedding-2", is_enabled=False),
        )
        session.commit()
        assert updated_model.model_name == "svc-model-2"
        assert updated_model.is_default is True
        assert updated_embedding.name == "svc-embedding-2"
        assert updated_embedding.is_enabled is False

    with container.session_factory() as session:
        assert any(item.model_name == "svc-model-2" for item in container.model_catalog_service.list_models(session))
        assert any(
            item.name == "svc-embedding-2"
            for item in container.embedding_provider_service.list_embedding_providers(session)
        )
