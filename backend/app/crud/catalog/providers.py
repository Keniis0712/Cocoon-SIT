from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelProvider


def list_model_providers(session: Session) -> list[ModelProvider]:
    return list(session.scalars(select(ModelProvider).order_by(ModelProvider.created_at.asc())).all())
