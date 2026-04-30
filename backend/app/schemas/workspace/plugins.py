from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class UserPluginConfigUpdate(BaseModel):
    config_json: dict = Field(default_factory=dict)


class UserPluginEventScheduleUpdate(BaseModel):
    schedule_mode: str
    schedule_interval_seconds: int | None = Field(default=None, ge=1)
    schedule_cron: str | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "UserPluginEventScheduleUpdate":
        if self.schedule_mode not in {"manual", "interval", "cron"}:
            raise ValueError("Invalid schedule_mode")
        if self.schedule_mode == "interval" and self.schedule_interval_seconds is None:
            raise ValueError("schedule_interval_seconds is required for interval schedule")
        if self.schedule_mode == "cron" and not (self.schedule_cron or "").strip():
            raise ValueError("schedule_cron is required for cron schedule")
        if self.schedule_mode != "cron":
            self.schedule_cron = None
        if self.schedule_mode != "interval":
            self.schedule_interval_seconds = None
        return self


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
    events: list["UserPluginEventOut"] = Field(default_factory=list)


class UserPluginEventOut(BaseModel):
    name: str
    mode: str
    function_name: str
    title: str
    description: str
    config_schema_json: dict
    default_config_json: dict
    schedule_mode: str
    schedule_interval_seconds: int | None
    schedule_cron: str | None


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
