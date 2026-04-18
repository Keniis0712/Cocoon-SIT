from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PromptTemplate


def list_prompt_templates(session: Session) -> list[PromptTemplate]:
    return list(session.scalars(select(PromptTemplate).order_by(PromptTemplate.template_type.asc())).all())
