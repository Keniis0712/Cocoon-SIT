from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.identity import new_id


class Character(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_summary: Mapped[str] = mapped_column(Text, default="")
    settings_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class CharacterAcl(Base, TimestampMixin):
    __tablename__ = "character_acl"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=True)
    can_use: Mapped[bool] = mapped_column(Boolean, default=True)


class ModelProvider(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "model_providers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), default="openai_compatible")
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    capabilities_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class AvailableModel(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "available_models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    provider_id: Mapped[str] = mapped_column(ForeignKey("model_providers.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_kind: Mapped[str] = mapped_column(String(64), default="chat")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class EmbeddingProvider(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "embedding_providers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), default="local_cpu")
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("model_providers.id"), nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderCredential(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "provider_credentials"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    provider_id: Mapped[str] = mapped_column(ForeignKey("model_providers.id"), unique=True, nullable=False)
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class TagRegistry(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "tag_registry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    tag_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="private")
    is_isolated: Mapped[bool] = mapped_column(Boolean, default=False)
    meta_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
