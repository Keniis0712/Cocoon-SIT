from sqlalchemy import select

from app.models import AvailableModel, ModelProvider, ProviderCredential
from app.services.providers.base import MockChatProvider
from app.services.providers.openai_compatible import OpenAICompatibleProvider


def test_model_selection_service_resolves_default_model_and_provider(client):
    container = client.app.state.container
    with container.session_factory() as session:
        model = session.scalars(select(AvailableModel)).first()
        resolved_model, provider = container.model_selection_service.resolve_chat_model(session, model.id)
        assert resolved_model.id == model.id
        assert provider.id == model.provider_id


def test_provider_runtime_config_service_decrypts_credentials(client):
    container = client.app.state.container
    with container.session_factory() as session:
        model = session.scalars(select(AvailableModel)).first()
        provider = session.get(ModelProvider, model.provider_id)
        session.add(
            ProviderCredential(
                provider_id=provider.id,
                secret_encrypted=container.secret_cipher.encrypt("provider-secret"),
                metadata_json={},
            )
        )
        session.commit()

    with container.session_factory() as session:
        model = session.scalars(select(AvailableModel)).first()
        provider = session.get(ModelProvider, model.provider_id)
        runtime_config = container.provider_runtime_config_service.build_chat_config(session, provider, model)
        assert runtime_config["api_key"] == "provider-secret"
        assert runtime_config["base_url"] == provider.base_url


def test_provider_factory_resolves_known_and_unknown_kinds(client):
    container = client.app.state.container

    assert isinstance(container.provider_factory.resolve_chat_provider("openai_compatible"), OpenAICompatibleProvider)
    assert isinstance(container.provider_factory.resolve_chat_provider("mock"), MockChatProvider)
    try:
        container.provider_factory.resolve_chat_provider("unknown-kind")
    except ValueError as exc:
        assert "Unsupported chat provider kind" in str(exc)
    else:
        raise AssertionError("Expected resolve_chat_provider to reject unknown provider kinds")
