from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.identity import new_id


class PromptTemplate(Base, TimestampMixin):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    template_type: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    active_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("prompt_template_revisions.id"), nullable=True
    )


class PromptTemplateRevision(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "prompt_template_revisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    template_id: Mapped[str] = mapped_column(ForeignKey("prompt_templates.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[list] = mapped_column(JSON, default=JsonDefaultMixin.json_list)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class PromptVariable(Base, TimestampMixin):
    __tablename__ = "prompt_variables"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    template_type: Mapped[str] = mapped_column(String(64), nullable=False)
    variable_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
