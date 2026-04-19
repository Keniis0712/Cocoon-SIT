from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import AvailableModel, ModelProvider
from app.schemas.catalog.models import AvailableModelOut
from app.schemas.catalog.providers import (
    ModelProviderCreate,
    ModelProviderOut,
    ProviderTestOut,
    ProviderTestRequest,
)


router = APIRouter()


@router.get("", response_model=list[ModelProviderOut])
def list_providers(
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:read")),
) -> list[ModelProvider]:
    return db.info["container"].provider_service.list_providers(db)


@router.post("", response_model=ModelProviderOut)
def create_provider(
    payload: ModelProviderCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> ModelProvider:
    return db.info["container"].provider_service.create_provider(db, payload)


@router.patch("/{provider_id}", response_model=ModelProviderOut)
def update_provider(
    provider_id: str,
    payload: ModelProviderCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> ModelProvider:
    return db.info["container"].provider_service.update_provider(db, provider_id, payload)


@router.delete("/{provider_id}", response_model=ModelProviderOut)
def delete_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> ModelProvider:
    return db.info["container"].provider_service.delete_provider(db, provider_id)


@router.post("/{provider_id}/sync-models", response_model=list[AvailableModelOut])
def sync_provider_models(
    provider_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> list[AvailableModel]:
    return db.info["container"].provider_service.sync_provider_models(db, provider_id)


@router.post("/{provider_id}/test", response_model=ProviderTestOut)
def test_provider(
    provider_id: str,
    payload: ProviderTestRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> ProviderTestOut:
    return db.info["container"].provider_service.test_provider(
        db,
        provider_id,
        selected_model_id=payload.selected_model_id,
        prompt=payload.prompt,
    )
