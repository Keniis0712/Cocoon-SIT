from __future__ import annotations

import json
from typing import Any


def extract_json_object(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if not raw:
        return None
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            raw = "\n".join(lines[1:-1]).strip()
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
    try:
        payload = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(raw[start:end + 1])
        except Exception:
            return None
    return payload if isinstance(payload, dict) else None
