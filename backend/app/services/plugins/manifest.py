from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class PluginEventManifest(BaseModel):
    name: str
    mode: Literal["short_lived", "daemon"]
    function_name: str
    title: str
    description: str
    config_schema: dict = Field(default_factory=dict)
    default_config: dict = Field(default_factory=dict)


class PluginPackageManifest(BaseModel):
    name: str
    version: str
    display_name: str
    plugin_type: Literal["external", "im"]
    entry_module: str
    config_schema: dict = Field(default_factory=dict)
    default_config: dict = Field(default_factory=dict)
    events: list[PluginEventManifest] = Field(default_factory=list)
    service_function: str | None = None

    @classmethod
    def load(cls, path: Path) -> "PluginPackageManifest":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid plugin.json: {exc}") from exc
        try:
            manifest = cls.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid plugin manifest: {exc}") from exc
        if manifest.plugin_type == "external" and not manifest.events:
            raise ValueError("External plugins must define at least one event in plugin.json")
        if manifest.plugin_type == "im" and not manifest.service_function:
            raise ValueError("IM plugins must define service_function in plugin.json")
        return manifest
