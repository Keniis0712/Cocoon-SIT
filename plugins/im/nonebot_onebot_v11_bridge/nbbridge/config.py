from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any
from urllib.parse import urlparse


PLUGIN_PLATFORM = "nonebot_onebot_v11"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def normalize_string_list(value: Any, *, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return list(default)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [text]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [str(parsed).strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return list(default)


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config or {})
    normalized["driver"] = str(normalized.get("driver") or "~aiohttp").strip() or "~aiohttp"
    normalized["onebot_ws_urls"] = normalize_string_list(normalized.get("onebot_ws_urls"), default=[])
    normalized["onebot_access_token"] = str(normalized.get("onebot_access_token") or "").strip()
    normalized["command_start"] = normalize_string_list(normalized.get("command_start"), default=["/"])
    normalized["command_sep"] = normalize_string_list(normalized.get("command_sep"), default=["."])
    normalized["default_owner_username"] = str(normalized.get("default_owner_username") or "").strip()
    normalized["default_model_id"] = str(normalized.get("default_model_id") or "").strip()
    normalized["private_cocoon_name_prefix"] = str(normalized.get("private_cocoon_name_prefix") or "QQ").strip() or "QQ"
    normalized["group_room_name_prefix"] = str(normalized.get("group_room_name_prefix") or "QQ Group").strip() or "QQ Group"
    normalized["message_priority"] = int(normalized.get("message_priority") or 95)
    return normalized


def validate_settings(ctx) -> str | None:
    config = normalize_config(ctx.plugin_config)
    if not config["onebot_ws_urls"]:
        return "onebot_ws_urls must include at least one WebSocket URL."
    for raw_url in config["onebot_ws_urls"]:
        parsed = urlparse(str(raw_url))
        if parsed.scheme not in {"ws", "wss"}:
            return "onebot_ws_urls must use ws:// or wss:// URLs."
        if not parsed.netloc:
            return "onebot_ws_urls entries must be valid WebSocket URLs."
    if not config["default_owner_username"]:
        return "default_owner_username is required."
    required_defaults = (config["default_model_id"],)
    if not all(required_defaults):
        return "default_model_id is required."
    return None
