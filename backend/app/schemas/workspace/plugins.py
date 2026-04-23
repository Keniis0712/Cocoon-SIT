from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserPluginConfigUpdate(BaseModel):
    config_json: dict = Field(default_factory=dict)


class ChatGroupPluginConfigUpdate(BaseModel):
    config_json: dict = Field(default_factory=dict)


class UserPluginTargetBindingCreate(BaseModel):
    target_type: str
    target_id: str


class UserPluginOut(BaseModel):
    id: str
    name: str
    display_name: str
    plugin_type: str
    status: str
    is_globally_visible: bool
    is_visible: bool
    is_enabled: bool
    config_schema_json: dict
    default_config_json: dict
    user_config_schema_json: dict
    user_default_config_json: dict
    user_config_json: dict
    user_error_text: str | None
    user_error_at: datetime | None


class UserPluginTargetBindingOut(BaseModel):
    id: str
    plugin_id: str
    scope_type: str
    scope_id: str
    target_type: str
    target_id: str
    target_name: str
    created_at: datetime
    updated_at: datetime


class ChatGroupPluginConfigOut(BaseModel):
    plugin_id: str
    chat_group_id: str
    is_enabled: bool
    config_schema_json: dict
    default_config_json: dict
    config_json: dict
    error_text: str | None
    error_at: datetime | None
