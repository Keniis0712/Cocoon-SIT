from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserPluginConfigUpdate(BaseModel):
    config_json: dict = Field(default_factory=dict)


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

