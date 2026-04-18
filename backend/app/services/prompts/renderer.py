from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any


PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
SENSITIVE_KEYS = {"secret", "token", "api_key", "password", "secret_encrypted"}


def sanitize_snapshot(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                result[key] = "***redacted***"
            else:
                result[key] = sanitize_snapshot(item)
        return result
    if isinstance(value, list):
        return [sanitize_snapshot(item) for item in value]
    return value


def find_placeholders(content: str) -> list[str]:
    return sorted(set(PLACEHOLDER_RE.findall(content)))


def coerce_render_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def render_template(content: str, variables: dict[str, Any]) -> str:
    sanitized = sanitize_snapshot(variables)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in sanitized:
            raise KeyError(key)
        return coerce_render_value(sanitized[key])

    return PLACEHOLDER_RE.sub(replace, content)

