from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.identity import new_id
from app.models.vector import EmbeddingVector

DEFAULT_RELATION_SCORE = 50
MIN_RELATION_SCORE = 0
MAX_RELATION_SCORE = 100


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


class ChatGroupRoom(Base, TimestampMixin):
    __tablename__ = "chat_group_rooms"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), nullable=False)
    selected_model_id: Mapped[str] = mapped_column(ForeignKey("available_models.id"), nullable=False)
    default_temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_context_messages: Mapped[int] = mapped_column(Integer, default=12)
    auto_compaction_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    external_platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_group_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ChatGroupMember(Base, TimestampMixin):
    __tablename__ = "chat_group_members"
    __table_args__ = (
        CheckConstraint("member_role IN ('admin', 'member')", name="ck_chat_group_members_role"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("chat_group_rooms.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    member_role: Mapped[str] = mapped_column(String(32), default="member")


class CocoonTagBinding(Base, TimestampMixin):
    __tablename__ = "cocoon_tag_bindings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str] = mapped_column(ForeignKey("cocoons.id"), nullable=False)
    tag_id: Mapped[str] = mapped_column(String(64), nullable=False)


class SessionState(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "session_states"
    __table_args__ = (
        CheckConstraint(
            "(cocoon_id IS NOT NULL AND chat_group_id IS NULL) OR (cocoon_id IS NULL AND chat_group_id IS NOT NULL)",
            name="ck_session_states_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True, unique=True)
    chat_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_group_rooms.id"),
        nullable=True,
        unique=True,
    )
    relation_score: Mapped[int] = mapped_column(Integer, default=DEFAULT_RELATION_SCORE)
    persona_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    active_tags_json: Mapped[list] = mapped_column(JSON, default=JsonDefaultMixin.json_list)
    current_wakeup_task_id: Mapped[str | None] = mapped_column(ForeignKey("wakeup_tasks.id"), nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("id", kwargs.get("cocoon_id") or kwargs.get("chat_group_id") or new_id())
        super().__init__(**kwargs)


class Message(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "(cocoon_id IS NOT NULL AND chat_group_id IS NULL) OR (cocoon_id IS NULL AND chat_group_id IS NOT NULL)",
            name="ck_messages_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True)
    chat_group_id: Mapped[str | None] = mapped_column(ForeignKey("chat_group_rooms.id"), nullable=True)
    action_id: Mapped[str | None] = mapped_column(ForeignKey("action_dispatches.id"), nullable=True)
    client_request_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    sender_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_thought: Mapped[bool] = mapped_column(Boolean, default=False)
    is_retracted: Mapped[bool] = mapped_column(Boolean, default=False)
    retracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    retracted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    retraction_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[list] = mapped_column(JSON, default=JsonDefaultMixin.json_list)


class MessageTag(Base, TimestampMixin):
    __tablename__ = "message_tags"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False)
    tag_id: Mapped[str] = mapped_column(String(64), nullable=False)


class MemoryChunk(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "memory_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True)
    chat_group_id: Mapped[str | None] = mapped_column(ForeignKey("chat_group_rooms.id"), nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    character_id: Mapped[str | None] = mapped_column(ForeignKey("characters.id"), nullable=True)
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
    __table_args__ = (
        CheckConstraint(
            "(cocoon_id IS NOT NULL AND chat_group_id IS NULL) OR (cocoon_id IS NULL AND chat_group_id IS NOT NULL)",
            name="ck_failed_rounds_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    cocoon_id: Mapped[str | None] = mapped_column(ForeignKey("cocoons.id"), nullable=True)
    chat_group_id: Mapped[str | None] = mapped_column(ForeignKey("chat_group_rooms.id"), nullable=True)
    action_id: Mapped[str | None] = mapped_column(ForeignKey("action_dispatches.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
