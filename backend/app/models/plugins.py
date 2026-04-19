from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.identity import new_id


class PluginDefinition(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "plugin_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
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
    __table_args__ = (
        UniqueConstraint("plugin_id", "event_name", "dedupe_key", name="uq_plugin_dispatch_records_dedupe"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugin_definitions.id"), nullable=False)
    plugin_version_id: Mapped[str] = mapped_column(ForeignKey("plugin_versions.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    wakeup_task_id: Mapped[str | None] = mapped_column(ForeignKey("wakeup_tasks.id"), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
