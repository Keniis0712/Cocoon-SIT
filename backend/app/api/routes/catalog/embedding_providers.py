from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import EmbeddingProvider
from app.schemas.catalog.embedding_providers import (
    EmbeddingProviderCreate,
    EmbeddingProviderOut,
    EmbeddingProviderUpdate,
)


router = APIRouter()


@router.get("/embedding-providers", response_model=list[EmbeddingProviderOut])
def list_embedding_providers(
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:read")),
) -> list[EmbeddingProvider]:
    return db.info["container"].embedding_provider_service.list_embedding_providers(db)


@router.post("/embedding-providers", response_model=EmbeddingProviderOut)
def create_embedding_provider(
    payload: EmbeddingProviderCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> EmbeddingProvider:
    return db.info["container"].embedding_provider_service.create_embedding_provider(db, payload)


@router.patch("/embedding-providers/{embedding_provider_id}", response_model=EmbeddingProviderOut)
def update_embedding_provider(
    embedding_provider_id: str,
    payload: EmbeddingProviderUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> EmbeddingProvider:
    return db.info["container"].embedding_provider_service.update_embedding_provider(
        db,
        embedding_provider_id,
        payload,
    )
