import pytest
from fastapi import HTTPException

from app.schemas.catalog.models import AvailableModelCreate, AvailableModelUpdate
from app.services.catalog.model_catalog_service import ModelCatalogService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_model_catalog_service_lists_creates_and_updates_models():
    session_factory = _session_factory()
    service = ModelCatalogService()

    with session_factory() as session:
        created = service.create_model(
            session,
            AvailableModelCreate(
                provider_id="provider-1",
                model_name="model-a",
                model_kind="chat",
                is_default=False,
                config_json={"temperature": 0.2},
            ),
        )
        other = service.create_model(
            session,
            AvailableModelCreate(
                provider_id="provider-1",
                model_name="model-b",
                model_kind="summary",
                is_default=True,
                config_json={},
            ),
        )
        listed = service.list_models(session)
        updated = service.update_model(
            session,
            created.id,
            AvailableModelUpdate(
                model_name="model-a2",
                model_kind="reasoning",
                is_default=True,
                config_json={"temperature": 0.6},
            ),
        )

        assert [model.id for model in listed] == [created.id, other.id]
        assert updated.model_name == "model-a2"
        assert updated.model_kind == "reasoning"
        assert updated.is_default is True
        assert updated.config_json == {"temperature": 0.6}


def test_model_catalog_service_update_raises_for_missing_model():
    session_factory = _session_factory()
    service = ModelCatalogService()

    with session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            service.update_model(session, "missing", AvailableModelUpdate(model_name="nope"))

    assert exc_info.value.status_code == 404
