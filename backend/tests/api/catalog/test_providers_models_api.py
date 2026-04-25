from types import SimpleNamespace

from sqlalchemy import select

from app.models import AvailableModel, EmbeddingProvider, ModelProvider


def test_provider_routes_cover_crud_sync_and_test(client, auth_headers, monkeypatch):
    container = client.app.state.container

    create = client.post(
        "/api/v1/providers",
        headers=auth_headers,
        json={"name": "api-provider", "kind": "mock", "base_url": None, "capabilities_json": {"streaming": True}},
    )
    assert create.status_code == 200, create.text
    provider_id = create.json()["id"]

    listing = client.get("/api/v1/providers", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    assert any(item["id"] == provider_id for item in listing.json())

    update = client.patch(
        f"/api/v1/providers/{provider_id}",
        headers=auth_headers,
        json={"name": "api-provider-updated", "kind": "mock", "base_url": "https://api.example", "capabilities_json": {}},
    )
    assert update.status_code == 200, update.text
    assert update.json()["name"] == "api-provider-updated"

    with container.session_factory() as session:
        model = AvailableModel(
            provider_id=provider_id,
            model_name="api-test-model",
            model_kind="chat",
            is_default=False,
            config_json={},
        )
        session.add(model)
        session.commit()
        model_id = model.id

    monkeypatch.setattr(container.provider_service, "_list_remote_models", lambda session, provider: ["synced-a", "synced-b"])
    sync = client.post(f"/api/v1/providers/{provider_id}/sync-models", headers=auth_headers)
    assert sync.status_code == 200, sync.text
    assert {item["model_name"] for item in sync.json()} >= {"synced-a", "synced-b"}

    test_provider = client.post(
        f"/api/v1/providers/{provider_id}/test",
        headers=auth_headers,
        json={"selected_model_id": model_id, "prompt": "hello"},
    )
    assert test_provider.status_code == 200, test_provider.text
    assert test_provider.json()["provider_id"] == provider_id

    delete = client.delete(f"/api/v1/providers/{provider_id}", headers=auth_headers)
    assert delete.status_code == 200, delete.text
    assert delete.json()["id"] == provider_id


def test_model_embedding_and_tag_api_routes_cover_remaining_operations(client, auth_headers):
    container = client.app.state.container
    with container.session_factory() as session:
        provider = session.scalar(select(ModelProvider).order_by(ModelProvider.created_at.asc()))
        assert provider is not None
        provider_id = provider.id

    create_model = client.post(
        "/api/v1/providers/models",
        headers=auth_headers,
        json={
            "provider_id": provider_id,
            "model_name": "api-model",
            "model_kind": "chat",
            "is_default": False,
            "config_json": {"reply_prefix": "api"},
        },
    )
    assert create_model.status_code == 200, create_model.text
    model_id = create_model.json()["id"]

    list_models = client.get("/api/v1/providers/models", headers=auth_headers)
    assert list_models.status_code == 200, list_models.text
    assert any(item["id"] == model_id for item in list_models.json())

    update_model = client.patch(
        f"/api/v1/providers/models/{model_id}",
        headers=auth_headers,
        json={"model_name": "api-model-updated", "is_default": True},
    )
    assert update_model.status_code == 200, update_model.text
    assert update_model.json()["model_name"] == "api-model-updated"

    create_embedding = client.post(
        "/api/v1/providers/embedding-providers",
        headers=auth_headers,
        json={
            "name": "api-embedding",
            "provider_id": provider_id,
            "model_name": "embed-api",
            "config_json": {"dims": 8},
            "is_enabled": True,
        },
    )
    assert create_embedding.status_code == 200, create_embedding.text
    embedding_id = create_embedding.json()["id"]

    list_embeddings = client.get("/api/v1/providers/embedding-providers", headers=auth_headers)
    assert list_embeddings.status_code == 200, list_embeddings.text
    assert any(item["id"] == embedding_id for item in list_embeddings.json())

    update_embedding = client.patch(
        f"/api/v1/providers/embedding-providers/{embedding_id}",
        headers=auth_headers,
        json={"name": "api-embedding-updated", "is_enabled": False},
    )
    assert update_embedding.status_code == 200, update_embedding.text
    assert update_embedding.json()["name"] == "api-embedding-updated"

    create_tag = client.post(
        "/api/v1/tags",
        headers=auth_headers,
        json={"tag_id": "api-tag", "brief": "API tag", "visibility": "private", "is_isolated": False, "meta_json": {}},
    )
    assert create_tag.status_code == 200, create_tag.text
    created_tag = create_tag.json()
    created_tag_id = created_tag["id"]

    list_tags = client.get("/api/v1/tags", headers=auth_headers)
    assert list_tags.status_code == 200, list_tags.text
    assert any(item["tag_id"] == "api-tag" for item in list_tags.json())

    update_tag = client.patch(
        f"/api/v1/tags/{created_tag_id}",
        headers=auth_headers,
        json={"brief": "API tag updated", "is_isolated": True},
    )
    assert update_tag.status_code == 200, update_tag.text
    assert update_tag.json()["brief"] == "API tag updated"

    delete_tag = client.delete(f"/api/v1/tags/{created_tag_id}", headers=auth_headers)
    assert delete_tag.status_code == 200, delete_tag.text
    assert delete_tag.json()["tag_id"] == "api-tag"
