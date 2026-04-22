from types import SimpleNamespace

import pytest

from app.services.providers.registry import ProviderRegistry


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


def test_provider_registry_resolves_chat_provider():
    model = SimpleNamespace(id="model-1", model_name="gpt-test")
    provider_record = SimpleNamespace(kind="mock")
    model_selection_service = SimpleNamespace(resolve_chat_model=lambda session, model_id: (model, provider_record))
    runtime_config_service = SimpleNamespace(build_chat_config=lambda session, provider, model: {"temperature": 0.2})
    factory = SimpleNamespace(resolve_chat_provider=lambda kind: f"provider:{kind}")
    registry = ProviderRegistry(model_selection_service, runtime_config_service, factory)

    provider, resolved_model, resolved_provider, config = registry.resolve_chat_provider(object(), "model-1")

    assert provider == "provider:mock"
    assert resolved_model is model
    assert resolved_provider is provider_record
    assert config == {"temperature": 0.2}


def test_provider_registry_resolves_single_embedding_provider():
    embedding_record = SimpleNamespace(kind="local_cpu", id="embed-1")
    session = SimpleNamespace(scalars=lambda query: _ScalarResult([embedding_record]))
    model_selection_service = SimpleNamespace()
    runtime_config_service = SimpleNamespace(build_embedding_config=lambda provider: {"dimensions": 8})
    factory = SimpleNamespace(resolve_embedding_provider=lambda kind: f"embedder:{kind}")
    registry = ProviderRegistry(model_selection_service, runtime_config_service, factory)

    provider, provider_record, config = registry.resolve_embedding_provider(session)

    assert provider == "embedder:local_cpu"
    assert provider_record is embedding_record
    assert config == {"dimensions": 8}


def test_provider_registry_returns_none_when_no_embedding_provider():
    session = SimpleNamespace(scalars=lambda query: _ScalarResult([]))
    registry = ProviderRegistry(SimpleNamespace(), SimpleNamespace(), SimpleNamespace())

    assert registry.resolve_embedding_provider(session) is None


def test_provider_registry_rejects_multiple_embedding_providers():
    session = SimpleNamespace(scalars=lambda query: _ScalarResult([SimpleNamespace(), SimpleNamespace()]))
    registry = ProviderRegistry(SimpleNamespace(), SimpleNamespace(), SimpleNamespace())

    with pytest.raises(ValueError, match="exactly one active embedding provider"):
        registry.resolve_embedding_provider(session)
