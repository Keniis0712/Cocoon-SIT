"""Model and provider record resolution for chat generation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AvailableModel, ModelProvider


class ModelSelectionService:
    """Loads the model/provider pair required for a chat generation request."""

    def resolve_chat_model(
        self,
        session: Session,
        model_id: str,
    ) -> tuple[AvailableModel, ModelProvider]:
        """Return the chat model and its owning provider record."""
        model = session.get(AvailableModel, model_id)
        if not model:
            raise ValueError(f"Unknown model: {model_id}")
        provider = session.get(ModelProvider, model.provider_id)
        if not provider:
            raise ValueError(f"Unknown provider for model: {model_id}")
        return model, provider
