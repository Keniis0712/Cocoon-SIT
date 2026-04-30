from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.identity import new_id


class PluginDefinition(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    plugin_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_module: Mapped[str] = mapped_column(String(255), nullable=False)
    service_function_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="disabled")
    install_source: Mapped[str] = mapped_column(String(32), default="zip")
    data_dir: Mapped[str] = mapped_column(String(1024), nullable=False)
    config_schema_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    default_config_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    config_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    user_config_schema_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    user_default_config_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    settings_validation_function_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_globally_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    active_version_id: Mapped[str | None] = mapped_column(ForeignKey("plugin_versions.id"), nullable=True)


class PluginVersion(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_versions"
    __table_args__ = (
        UniqueConstraint("plugin_id", "version", name="uq_plugin_versions_plugin_id_version"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    source_zip_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    manifest_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    install_status: Mapped[str] = mapped_column(String(32), default="installed")
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class PluginEventDefinition(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_event_definitions"
    __table_args__ = (
        UniqueConstraint("plugin_version_id", "name", name="uq_plugin_event_definitions_version_name"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    plugin_version_id: Mapped[str] = mapped_column(ForeignKey("plugin_versions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    function_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    config_schema_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    default_config_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class PluginEventConfig(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_event_configs"
    __table_args__ = (
        UniqueConstraint("plugin_id", "event_name", name="uq_plugin_event_configs_plugin_id_event_name"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class PluginRunState(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_run_states"
    __table_args__ = (
        UniqueConstraint("plugin_id", name="uq_plugin_run_states_plugin_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(ForeignKey("plugin_versions.id"), nullable=True)
    process_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="stopped")
    heartbeat_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class PluginDispatchRecord(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_dispatch_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    plugin_version_id: Mapped[str] = mapped_column(ForeignKey("plugin_versions.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    wakeup_task_id: Mapped[str | None] = mapped_column(ForeignKey("wakeup_tasks.id"), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class PluginImDeliveryOutbox(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_im_delivery_outbox"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    action_id: Mapped[str | None] = mapped_column(ForeignKey("action_dispatches.id"), nullable=True)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    payload_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_error_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class PluginImTargetRoute(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_im_target_routes"
    __table_args__ = (
        UniqueConstraint(
            "plugin_id",
            "external_platform",
            "conversation_kind",
            "external_account_id",
            "external_conversation_id",
            name="uq_plugin_im_target_routes_plugin_conversation",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_platform: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    route_metadata_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class PluginUserConfig(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_user_configs"
    __table_args__ = (
        UniqueConstraint("plugin_id", "user_id", name="uq_plugin_user_configs_plugin_id_user_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    validation_error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    runtime_error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PluginUserEventConfig(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_user_event_configs"
    __table_args__ = (
        UniqueConstraint(
            "plugin_id",
            "user_id",
            "event_name",
            name="uq_plugin_user_event_configs_plugin_id_user_id_event_name",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    schedule_mode: Mapped[str] = mapped_column(String(32), default="manual")
    schedule_interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_cron: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PluginChatGroupConfig(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_chat_group_configs"
    __table_args__ = (
        UniqueConstraint("plugin_id", "chat_group_id", name="uq_plugin_chat_group_configs_plugin_id_chat_group_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    chat_group_id: Mapped[str] = mapped_column(ForeignKey("chat_group_rooms.id"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    validation_error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    runtime_error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PluginGroupVisibility(Base, TimestampMixin):
    __tablename__ = "plugin_group_visibility"
    __table_args__ = (
        UniqueConstraint("plugin_id", "group_id", name="uq_plugin_group_visibility_plugin_id_group_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    group_id: Mapped[str] = mapped_column(ForeignKey("user_groups.id"), nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)


class PluginTargetBinding(Base, TimestampMixin):
    __tablename__ = "plugin_target_bindings"
    __table_args__ = (
        UniqueConstraint(
            "plugin_id",
            "scope_type",
            "scope_id",
            "target_type",
            "target_id",
            name="uq_plugin_target_bindings_plugin_scope_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
