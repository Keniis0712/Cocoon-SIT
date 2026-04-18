"""Available-model catalog administration service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AvailableModel
from app.schemas.catalog.models import AvailableModelCreate, AvailableModelUpdate


class ModelCatalogService:
    """Creates, lists, and updates available chat models."""

    def list_models(self, session: Session) -> list[AvailableModel]:
        """Return models ordered by creation time."""
        return list(session.scalars(select(AvailableModel).order_by(AvailableModel.created_at.asc())).all())

    def create_model(self, session: Session, payload: AvailableModelCreate) -> AvailableModel:
        """Create an available model entry."""
        model = AvailableModel(
            provider_id=payload.provider_id,
            model_name=payload.model_name,
            model_kind=payload.model_kind,
            is_default=payload.is_default,
            config_json=payload.config_json,
        )
        session.add(model)
        session.flush()
        return model

    def update_model(self, session: Session, model_id: str, payload: AvailableModelUpdate) -> AvailableModel:
        """Patch an available model entry."""
        model = session.get(AvailableModel, model_id)
        if not model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        if payload.model_name is not None:
            model.model_name = payload.model_name
        if payload.model_kind is not None:
            model.model_kind = payload.model_kind
        if payload.is_default is not None:
            model.is_default = payload.is_default
        if payload.config_json is not None:
            model.config_json = payload.config_json
        session.flush()
        return model
