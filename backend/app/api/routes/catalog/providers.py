from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import ModelProvider
from app.schemas.catalog.providers import ModelProviderCreate, ModelProviderOut


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
