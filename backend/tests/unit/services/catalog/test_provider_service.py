from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.models import AvailableModel, Cocoon, EmbeddingProvider, ModelProvider, ProviderCredential
from app.schemas.catalog.providers import ModelProviderCreate
from app.services.catalog.provider_service import ProviderService
from app.services.providers.base import ProviderTextResponse, ProviderUsage
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_provider_service_create_update_list_and_test_provider(monkeypatch):
    session_factory = _session_factory()
    chat_provider_calls = []

    class _FakeChatProvider:
        def generate_text(self, **kwargs):
            chat_provider_calls.append(kwargs)
            return ProviderTextResponse(
                text="connected",
                chunks=["connected"],
                raw_response={"provider": "mock"},
                usage=ProviderUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
            )

    runtime_config_service = SimpleNamespace(
        build_chat_config=lambda session, provider, model: {"api_key": "secret", "base_url": provider.base_url}
    )
    provider_factory = SimpleNamespace(resolve_chat_provider=lambda kind: _FakeChatProvider())
    service = ProviderService(runtime_config_service, provider_factory)

    with session_factory() as session:
        provider = service.create_provider(
            session,
            ModelProviderCreate(
                name="provider-a",
                kind="mock",
                base_url="https://example.test",
                capabilities_json={"streaming": True},
            ),
        )
        session.flush()
        model = AvailableModel(
            provider_id=provider.id,
            model_name="model-a",
            model_kind="chat",
            is_default=False,
            config_json={"temperature": 0.2},
        )
        session.add(model)
        session.flush()

        updated = service.update_provider(
            session,
            provider.id,
            ModelProviderCreate(
                name="provider-b",
                kind="mock",
                base_url="https://example-updated.test",
                capabilities_json={"streaming": False},
            ),
        )
        tested = service.test_provider(
            session,
            provider.id,
            selected_model_id=model.id,
            prompt="hello provider",
        )

        assert [item.id for item in service.list_providers(session)] == [provider.id]
        assert updated.name == "provider-b"
        assert tested.reply == "connected"
        assert tested.model_name == "model-a"
        assert chat_provider_calls[0]["messages"] == [{"role": "user", "content": "hello provider"}]
        assert chat_provider_calls[0]["provider_config"] == {
            "api_key": "secret",
            "base_url": "https://example-updated.test",
        }


def test_provider_service_delete_rejects_missing_and_referenced_records():
    session_factory = _session_factory()
    service = ProviderService(SimpleNamespace(), SimpleNamespace())

    with session_factory() as session:
        with pytest.raises(HTTPException) as missing_exc:
            service.delete_provider(session, "missing-provider")
        assert missing_exc.value.status_code == 404

        in_use_provider = ModelProvider(name="provider-in-use", kind="mock", base_url=None, capabilities_json={})
        session.add(in_use_provider)
        session.flush()
        selected_model = AvailableModel(
            provider_id=in_use_provider.id,
            model_name="model-in-use",
            model_kind="chat",
            is_default=False,
            config_json={},
        )
        session.add(selected_model)
        session.flush()
        session.add(
            Cocoon(
                name="using-cocoon",
                owner_user_id="user-1",
                character_id="character-1",
                selected_model_id=selected_model.id,
            )
        )
        session.flush()

        with pytest.raises(HTTPException) as in_use_exc:
            service.delete_provider(session, in_use_provider.id)
        assert in_use_exc.value.status_code == 409

        embedding_provider = ModelProvider(name="provider-embedding", kind="mock", base_url=None, capabilities_json={})
        session.add(embedding_provider)
        session.flush()
        session.add(
            EmbeddingProvider(
                name="embed-provider",
                provider_id=embedding_provider.id,
                model_name="embed-model",
                config_json={},
                is_enabled=True,
            )
        )
        session.flush()

        with pytest.raises(HTTPException) as embedding_exc:
            service.delete_provider(session, embedding_provider.id)
        assert embedding_exc.value.status_code == 409


def test_provider_service_delete_removes_models_and_credentials():
    session_factory = _session_factory()
    service = ProviderService(SimpleNamespace(), SimpleNamespace())

    with session_factory() as session:
        provider = ModelProvider(name="provider-delete", kind="mock", base_url=None, capabilities_json={})
        session.add(provider)
        session.flush()
        session.add(
            AvailableModel(
                provider_id=provider.id,
                model_name="deletable-model",
                model_kind="chat",
                is_default=False,
                config_json={},
            )
        )
        session.add(
            ProviderCredential(
                provider_id=provider.id,
                secret_encrypted="enc-secret",
                metadata_json={},
            )
        )
        session.flush()

        deleted = service.delete_provider(session, provider.id)

        assert deleted.id == provider.id
        assert session.get(ModelProvider, provider.id) is None
        assert not list(session.query(AvailableModel).filter(AvailableModel.provider_id == provider.id).all())
        assert not list(session.query(ProviderCredential).filter(ProviderCredential.provider_id == provider.id).all())


def test_provider_service_sync_provider_models_validates_provider_prerequisites():
    session_factory = _session_factory()
    runtime_config_service = SimpleNamespace(secret_cipher=SimpleNamespace(decrypt=lambda value: "decrypted"))
    service = ProviderService(runtime_config_service, SimpleNamespace())

    with session_factory() as session:
        with pytest.raises(HTTPException) as missing_exc:
            service.sync_provider_models(session, "missing")
        assert missing_exc.value.status_code == 404

        mock_provider = ModelProvider(name="mock-provider", kind="mock", base_url=None, capabilities_json={})
        session.add(mock_provider)
        session.flush()
        with pytest.raises(HTTPException) as kind_exc:
            service.sync_provider_models(session, mock_provider.id)
        assert kind_exc.value.status_code == 400

        openai_provider = ModelProvider(
            name="openai-provider",
            kind="openai_compatible",
            base_url=None,
            capabilities_json={},
        )
        session.add(openai_provider)
        session.flush()
        with pytest.raises(HTTPException) as base_url_exc:
            service.sync_provider_models(session, openai_provider.id)
        assert base_url_exc.value.status_code == 400
        assert "base_url" in base_url_exc.value.detail

        openai_provider.base_url = "https://provider.example"
        with pytest.raises(HTTPException) as credential_exc:
            service.sync_provider_models(session, openai_provider.id)
        assert credential_exc.value.status_code == 400
        assert "credential" in credential_exc.value.detail


def test_provider_service_sync_provider_models_handles_http_errors_and_empty_results(monkeypatch):
    session_factory = _session_factory()
    runtime_config_service = SimpleNamespace(secret_cipher=SimpleNamespace(decrypt=lambda value: "decrypted"))
    service = ProviderService(runtime_config_service, SimpleNamespace())

    class _ErrorClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise httpx.HTTPError("network boom")

    class _EmptyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"name": "missing-id"}, "bad-item"]}

    class _EmptyClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            return _EmptyResponse()

    with session_factory() as session:
        provider = ModelProvider(
            name="openai-provider",
            kind="openai_compatible",
            base_url="https://provider.example",
            capabilities_json={},
        )
        session.add(provider)
        session.flush()
        session.add(ProviderCredential(provider_id=provider.id, secret_encrypted="enc", metadata_json={}))
        session.flush()

        monkeypatch.setattr("app.services.catalog.provider_service.httpx.Client", _ErrorClient)
        with pytest.raises(HTTPException) as http_exc:
            service.sync_provider_models(session, provider.id)
        assert http_exc.value.status_code == 502

        monkeypatch.setattr("app.services.catalog.provider_service.httpx.Client", _EmptyClient)
        with pytest.raises(HTTPException) as empty_exc:
            service.sync_provider_models(session, provider.id)
        assert empty_exc.value.status_code == 502
        assert "no models" in empty_exc.value.detail.lower()


def test_provider_service_sync_provider_models_upserts_remote_models(monkeypatch):
    session_factory = _session_factory()
    runtime_config_service = SimpleNamespace(secret_cipher=SimpleNamespace(decrypt=lambda value: "decrypted"))
    service = ProviderService(runtime_config_service, SimpleNamespace())

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"id": "b-model"},
                    {"id": "a-model"},
                    {"id": "b-model"},
                    {"id": ""},
                    "bad-item",
                ]
            }

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers):
            self.calls.append((url, headers))
            return _Response()

    monkeypatch.setattr("app.services.catalog.provider_service.httpx.Client", _Client)

    with session_factory() as session:
        provider = ModelProvider(
            name="openai-provider",
            kind="openai_compatible",
            base_url="https://provider.example/",
            capabilities_json={},
        )
        session.add(provider)
        session.flush()
        session.add(ProviderCredential(provider_id=provider.id, secret_encrypted="enc", metadata_json={}))
        session.add(
            AvailableModel(
                provider_id=provider.id,
                model_name="a-model",
                model_kind="chat",
                is_default=False,
                config_json={},
            )
        )
        session.flush()

        synced = service.sync_provider_models(session, provider.id)

        assert [item.model_name for item in synced] == ["a-model", "b-model"]
