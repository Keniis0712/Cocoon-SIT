import pytest

from app.services.providers.model_selection_service import ModelSelectionService


def test_model_selection_service_resolves_model_and_provider():
    model = type("Model", (), {"provider_id": "provider-1"})()
    provider = object()

    class _Session:
        def get(self, model_type, key):
            if key == "model-1":
                return model
            if key == "provider-1":
                return provider
            return None

    service = ModelSelectionService()

    resolved_model, resolved_provider = service.resolve_chat_model(_Session(), "model-1")

    assert resolved_model is model
    assert resolved_provider is provider


def test_model_selection_service_rejects_missing_records():
    class _MissingModelSession:
        def get(self, model_type, key):
            return None

    service = ModelSelectionService()

    with pytest.raises(ValueError, match="Unknown model"):
        service.resolve_chat_model(_MissingModelSession(), "model-1")

    class _MissingProviderSession:
        def get(self, model_type, key):
            if key == "model-1":
                return type("Model", (), {"provider_id": "provider-1"})()
            return None

    with pytest.raises(ValueError, match="Unknown provider for model"):
        service.resolve_chat_model(_MissingProviderSession(), "model-1")
