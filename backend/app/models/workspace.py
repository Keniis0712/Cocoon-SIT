from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.identity import new_id
from app.models.vector import EmbeddingVector


class Cocoon(Base, TimestampMixin):
    __tablename__ = "cocoons"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), nullable=False)
    selected_model_id: Mapped[str] = mapped_column(ForeignKey("available_models.id"), nullable=False)
    summary_model_id: Mapped[str | None] = mapped_column(ForeignKey("available_models.id"), nullable=True)
    default_temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_context_messages: Mapped[int] = mapped_column(Integer, default=12)
    auto_compaction_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rollback_anchor_msg_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"), nullable=True)


class CocoonTagBinding(Base, TimestampMixin):
    __tablename__ = "cocoon_tag_bindings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    tag_id: Mapped[str] = mapped_column(String(64), nullable=False)


class SessionState(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "session_states"

    cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), primary_key=True)
    relation_score: Mapped[int] = mapped_column(Integer, default=0)
    persona_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    active_tags_json: Mapped[list] = mapped_column(JSON, default=JsonDefaultMixin.json_list)
    current_wakeup_task_id: Mapped[str | None] = mapped_column(ForeignKey("wakeup_tasks.id"), nullable=True)


class Message(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    action_id: Mapped[str | None] = mapped_column(ForeignKey("action_dispatches.id"), nullable=True)
    client_request_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_thought: Mapped[bool] = mapped_column(Boolean, default=False)
    tags_json: Mapped[list] = mapped_column(JSON, default=JsonDefaultMixin.json_list)


class MessageTag(Base, TimestampMixin):
    __tablename__ = "message_tags"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False)
    tag_id: Mapped[str] = mapped_column(String(64), nullable=False)


class MemoryChunk(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "memory_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    source_message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[list] = mapped_column(JSON, default=JsonDefaultMixin.json_list)
    meta_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    embedding_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)


class MemoryEmbedding(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "memory_embeddings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    memory_chunk_id: Mapped[str] = mapped_column(ForeignKey("memory_chunks.id"), nullable=False, unique=True)
    embedding_provider_id: Mapped[str] = mapped_column(ForeignKey("embedding_providers.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingVector(), nullable=True)
    usage_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    meta_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class MemoryTag(Base, TimestampMixin):
    __tablename__ = "memory_tags"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    memory_chunk_id: Mapped[str] = mapped_column(ForeignKey("memory_chunks.id"), nullable=False)
    tag_id: Mapped[str] = mapped_column(String(64), nullable=False)


class FailedRound(Base, TimestampMixin):
    __tablename__ = "failed_rounds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    action_id: Mapped[str | None] = mapped_column(ForeignKey("action_dispatches.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
