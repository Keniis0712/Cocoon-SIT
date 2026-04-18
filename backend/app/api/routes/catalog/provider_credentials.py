from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.schemas.catalog.providers import ProviderCredentialCreate, ProviderCredentialOut


router = APIRouter()


@router.post("/{provider_id}/credentials", response_model=ProviderCredentialOut)
def set_provider_credential(
    provider_id: str,
    payload: ProviderCredentialCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> ProviderCredentialOut:
    return db.info["container"].provider_credential_service.set_credential(db, provider_id, payload)


@router.get("/{provider_id}/credentials", response_model=ProviderCredentialOut)
def get_provider_credential(
    provider_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> ProviderCredentialOut:
    return db.info["container"].provider_credential_service.get_credential(db, provider_id)
