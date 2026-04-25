from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.runtime.types import ContextPackage

_TAG_VISIBILITY_EXPLANATIONS = {
    "public": (
        "Visible across both private cocoons and group conversations, "
        "so it is generally safe to mention."
    ),
    "group_acl": (
        "Visible in cocoons, and only visible in explicitly allowed chat-group conversations."
    ),
    "private": (
        "Strictly private to its originating scope and should not be exposed "
        "or relied on outside that private boundary."
    ),
}

_PROMPT_HIDDEN_KEYS = {
    "id",
    "action_id",
    "api_key",
    "base_url",
    "character_id",
    "client_request_id",
    "debounce_key",
    "embedding_provider_id",
    "memory_chunk_id",
    "message_id",
    "memory_owner_user_id",
    "model_name",
    "output_name",
    "owner_user_id",
    "provider_id",
    "provider_kind",
    "sender_display_name",
    "sender_user_id",
    "source_cocoon_id",
    "source_message_id",
    "source_target_id",
    "superseded_by_task_id",
    "target_id",
}
_PROMPT_PROVIDER_KEYWORDS = ("provider", "model", "key", "secret", "token", "url", "endpoint")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)


def _tag_catalog(context: ContextPackage) -> dict[str, dict[str, Any]]:
    payload = context.external_context.get("tag_catalog_by_ref") or {}
    return payload if isinstance(payload, dict) else {}


def _resolve_tag_name(tag_payload: dict[str, Any], tag_ref: str) -> str:
    meta_json = tag_payload.get("meta_json")
    if isinstance(meta_json, dict):
        for key in ("name", "title", "display_name", "label"):
            value = meta_json.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    tag_id = tag_payload.get("tag_id")
    if isinstance(tag_id, str) and tag_id.strip():
        return tag_id.strip()
    return tag_ref


def _visibility_description(visibility: str) -> str:
    return _TAG_VISIBILITY_EXPLANATIONS.get(
        visibility,
        "Visibility is custom; treat it as a scoped tag and avoid mentioning it "
        "unless the current context clearly allows it.",
    )


def _serialize_tag(
    tag_ref: str, context: ContextPackage, catalog: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    tag_payload = catalog.get(tag_ref) or {}
    visibility = str(tag_payload.get("visibility") or "private")
    return {
        "name": _resolve_tag_name(tag_payload, tag_ref),
        "brief": tag_payload.get("brief") or "",
        "visibility": {
            "label": visibility.replace("_", " "),
            "description": _visibility_description(visibility),
        },
        "is_isolated": bool(tag_payload.get("is_isolated", visibility == "private")),
        "mentionable_in_current_target": _mentionable_for_target([tag_ref], context, catalog),
    }


def _mentionable_for_target(
    tag_refs: list[str], context: ContextPackage, catalog: dict[str, dict[str, Any]]
) -> bool:
    if not tag_refs:
        return True
    for tag_ref in tag_refs:
        payload = catalog.get(tag_ref) or {}
        if payload.get("visible_in_target") is False:
            return False
    return True


def _serialize_tags(
    tag_refs: list[str], context: ContextPackage, catalog: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    return [_serialize_tag(tag_ref, context, catalog) for tag_ref in tag_refs]


def _looks_like_uuid(value: str) -> bool:
    return bool(_UUID_RE.fullmatch(value.strip()))


def _sanitize_prompt_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _sanitize_prompt_dict(value)
    if isinstance(value, list):
        return [item for raw in value if (item := _sanitize_prompt_value(raw)) is not None]
    if isinstance(value, str) and _looks_like_uuid(value):
        return None
    return value


def _sanitize_prompt_dict(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        normalized = key.casefold()
        if (
            key in _PROMPT_HIDDEN_KEYS
            or normalized.endswith("_id")
            or normalized.endswith("_ids")
            or any(token in normalized for token in _PROMPT_PROVIDER_KEYWORDS)
        ):
            continue
        sanitized = _sanitize_prompt_value(value)
        if sanitized is None:
            continue
        cleaned[key] = sanitized
    return cleaned


def _sanitize_provider_capabilities(payload: dict[str, Any] | None) -> dict[str, Any]:
    return _sanitize_prompt_dict(payload or {})


def _normalize_timezone_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    timezone = value.strip()
    if not timezone:
        return None
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return None
    return timezone


def resolve_runtime_timezone(context: ContextPackage) -> str:
    candidates: list[Any] = [context.runtime_event.payload.get("timezone")]
    wakeup_context = context.external_context.get("wakeup_context")
    if isinstance(wakeup_context, dict):
        candidates.append(wakeup_context.get("timezone"))
    candidates.append(context.external_context.get("runtime_timezone_fallback"))
    for candidate in candidates:
        if timezone := _normalize_timezone_name(candidate):
            return timezone
    return "UTC"


def build_runtime_clock_payload(
    context: ContextPackage,
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    timezone_name = resolve_runtime_timezone(context)
    current = now or datetime.now(UTC)
    current = current.replace(tzinfo=UTC) if current.tzinfo is None else current.astimezone(UTC)
    local_time = current.astimezone(ZoneInfo(timezone_name))
    return {
        "timezone": timezone_name,
        "local_time": local_time.strftime("%Y-%m-%d %H:%M:%S"),
        "local_time_iso": local_time.isoformat(timespec="seconds"),
    }


def _compact_runtime_event_payload(runtime_event: dict[str, Any] | None) -> dict[str, Any]:
    payload = runtime_event if isinstance(runtime_event, dict) else {}
    compact: dict[str, Any] = {}
    for key in (
        "event_type",
        "target_type",
        "reason",
        "trigger_kind",
        "scheduled_by",
        "source_event_type",
        "timezone",
    ):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            compact[key] = value
    return compact


def _compact_wakeup_context_payload(wakeup_context: dict[str, Any] | None) -> dict[str, Any]:
    payload = wakeup_context if isinstance(wakeup_context, dict) else {}
    compact: dict[str, Any] = {}
    for key in (
        "reason",
        "trigger_kind",
        "scheduled_by",
        "source_event_type",
        "idle_summary",
        "silence_started_at",
        "silence_deadline_at",
        "timezone",
    ):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            compact[key] = value
    return compact


def _compact_pending_wakeup_payload(tasks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        item = {
            "id": task.get("id"),
            "run_at": task.get("run_at"),
            "reason": task.get("reason"),
            "status": task.get("status"),
        }
        compact.append(
            {key: value for key, value in item.items() if value not in (None, "", [], {})}
        )
    return compact


def _tag_names(tag_payloads: list[Any] | None) -> list[str]:
    names: list[str] = []
    for item in tag_payloads or []:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
        elif isinstance(item, str) and item.strip():
            names.append(item.strip())
    return names
