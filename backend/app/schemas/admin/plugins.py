from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PluginConfigUpdate(BaseModel):
    config_json: dict = Field(default_factory=dict)


class PluginEventConfigUpdate(BaseModel):
    config_json: dict = Field(default_factory=dict)


class PluginVersionOut(ORMModel):
    id: str
    plugin_id: str
    version: str
    source_zip_path: str
    extracted_path: str
    manifest_path: str
    install_status: str
    error_text: str | None
    metadata_json: dict
    created_at: datetime


class PluginEventOut(BaseModel):
    name: str
    mode: str
    function_name: str
    title: str
    description: str
    config_schema_json: dict
    default_config_json: dict
    config_json: dict
    is_enabled: bool


class PluginRunStateOut(ORMModel):
    id: str
    plugin_id: str
    current_version_id: str | None
    process_type: str | None
    pid: int | None
    status: str
    heartbeat_at: str | None
    error_text: str | None
    meta_json: dict
    updated_at: datetime


class PluginListItemOut(ORMModel):
    id: str
    name: str
    display_name: str
    plugin_type: str
    entry_module: str
    service_function_name: str | None
    status: str
    install_source: str
    data_dir: str
    config_schema_json: dict
    default_config_json: dict
    config_json: dict
    active_version_id: str | None
    created_at: datetime
    updated_at: datetime


class PluginDetailOut(PluginListItemOut):
    active_version: PluginVersionOut | None = None
    versions: list[PluginVersionOut] = Field(default_factory=list)
    events: list[PluginEventOut] = Field(default_factory=list)
    run_state: PluginRunStateOut | None = None


class PluginInstallResult(BaseModel):
    plugin: PluginDetailOut


class PluginSharedPackageOut(BaseModel):
    name: str
    normalized_name: str
    version: str
    path: str
    reference_count: int
    size_bytes: int
