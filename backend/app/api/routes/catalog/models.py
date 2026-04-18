from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import AvailableModel
from app.schemas.catalog.models import AvailableModelCreate, AvailableModelOut, AvailableModelUpdate


router = APIRouter()


@router.get("/models", response_model=list[AvailableModelOut])
def list_models(
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:read")),
) -> list[AvailableModel]:
    return db.info["container"].model_catalog_service.list_models(db)


@router.post("/models", response_model=AvailableModelOut)
def create_model(
    payload: AvailableModelCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> AvailableModel:
    return db.info["container"].model_catalog_service.create_model(db, payload)


@router.patch("/models/{model_id}", response_model=AvailableModelOut)
def update_model(
    model_id: str,
    payload: AvailableModelUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("providers:write")),
) -> AvailableModel:
    return db.info["container"].model_catalog_service.update_model(db, model_id, payload)
