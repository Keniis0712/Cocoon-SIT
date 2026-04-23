from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditRun, AuditStep, PromptTemplate, PromptTemplateRevision
from app.services.audit.service import AuditService
from app.services.runtime.types import ContextPackage


_TAG_VISIBILITY_EXPLANATIONS = {
    "public": "Visible across both private cocoons and group conversations, so it is generally safe to mention.",
    "group_private": "Visible inside private cocoon contexts, but should not be surfaced into shared chat-group conversations.",
    "private": "Strictly private to its originating scope and should not be exposed or relied on outside that private boundary.",
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
        "Visibility is custom; treat it as a scoped tag and avoid mentioning it unless the current context clearly allows it.",
    )


def _serialize_tag(tag_ref: str, context: ContextPackage, catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
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


def _mentionable_for_target(tag_refs: list[str], context: ContextPackage, catalog: dict[str, dict[str, Any]]) -> bool:
    if not tag_refs:
        return True
    allowed = {"public"} if context.target_type == "chat_group" else {"public", "group_private"}
    for tag_ref in tag_refs:
        visibility = str((catalog.get(tag_ref) or {}).get("visibility") or "private")
        if visibility not in allowed:
            return False
    return True


def _serialize_tags(tag_refs: list[str], context: ContextPackage, catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
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


def _character_settings_payload(context: ContextPackage) -> dict[str, Any]:
    payload = dict(context.character.settings_json or {})
    prompt_summary = (context.character.prompt_summary or "").strip()
    personality_prompt = str(payload.get("personality_prompt") or "").strip()
    if prompt_summary and prompt_summary != personality_prompt:
        payload["prompt_summary"] = prompt_summary
    elif "prompt_summary" in payload and str(payload.get("prompt_summary") or "").strip() == personality_prompt:
        payload.pop("prompt_summary", None)
    return payload


def _participant_alias(context: ContextPackage, sender_user_id: str | None) -> str | None:
    if not sender_user_id:
        return None
    sender = str(sender_user_id)
    if context.target_type == "cocoon":
        return "you"
    participants: dict[str, str] = {}
    next_index = 1
    for message in context.visible_messages:
        user_id = getattr(message, "sender_user_id", None)
        if message.role != "user" or not user_id:
            continue
        normalized = str(user_id)
        if normalized not in participants:
            participants[normalized] = f"participant_{next_index}"
            next_index += 1
    return participants.get(sender, "participant")


def _runtime_message_payload(message, context: ContextPackage, catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tag_refs = list(message.tags_json or [])
    retracted_suffix = "\n\n[system note: this message was later retracted]" if message.is_retracted else ""
    payload = {
        "role": message.role,
        "content": f"{message.content}{retracted_suffix}",
        "is_retracted": message.is_retracted,
        "tags": _serialize_tags(tag_refs, context, catalog),
        "mentionable_in_current_target": _mentionable_for_target(tag_refs, context, catalog),
    }
    if alias := _participant_alias(context, getattr(message, "sender_user_id", None)):
        payload["speaker"] = alias
    return payload


def _runtime_memory_payload(memory, context: ContextPackage, catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tag_refs = list(memory.tags_json or [])
    return {
        "scope": memory.scope,
        "summary": memory.summary,
        "content": memory.content,
        "tags": _serialize_tags(tag_refs, context, catalog),
        "mentionable_in_current_target": _mentionable_for_target(tag_refs, context, catalog),
        "source": "chat_group" if memory.chat_group_id else "cocoon",
    }


def _merge_context_payload(context: ContextPackage, catalog: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    payload = context.external_context.get("merge_context")
    if not isinstance(payload, dict):
        return payload
    source_state = payload.get("source_state")
    source_state_payload = source_state if isinstance(source_state, dict) else {}
    source_active_tags = source_state_payload.get("active_tags_json")
    tag_refs = source_active_tags if isinstance(source_active_tags, list) else []
    return {
        **_sanitize_prompt_dict(payload),
        "source_state": {
            "relation_score": source_state_payload.get("relation_score", 0),
            "persona_json": _sanitize_prompt_value(source_state_payload.get("persona_json", {})),
            "active_tags": _serialize_tags(tag_refs, context, catalog),
        },
    }


def _runtime_event_payload(context: ContextPackage) -> dict[str, Any]:
    return {
        "event_type": context.runtime_event.event_type,
        "target_type": context.runtime_event.target_type,
        **_sanitize_prompt_dict(context.runtime_event.payload),
    }


def _pending_wakeup_payload(tasks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        item = {
            "run_at": task.get("run_at"),
            "reason": task.get("reason"),
            "status": task.get("status"),
            "has_payload": bool(task.get("payload_json")),
        }
        if task.get("cancelled_at"):
            item["cancelled_at"] = task.get("cancelled_at")
        sanitized.append(item)
    return sanitized


def build_provider_message_payload(message, context: ContextPackage) -> dict[str, str]:
    content = message.content
    if message.role == "user" and (alias := _participant_alias(context, getattr(message, "sender_user_id", None))):
        content = f"[speaker:{alias}] {content}"
    if message.is_retracted:
        content = f"{content}\n\n[system note: this message was later retracted]"
    return {"role": message.role, "content": content}


def build_runtime_prompt_variables(
    context: ContextPackage,
    *,
    provider_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = _tag_catalog(context)
    pending_wakeups = _pending_wakeup_payload(context.external_context.get("pending_wakeups", []))
    return {
        "character_settings": _character_settings_payload(context),
        "conversation_target": {
            "type": context.target_type,
            "name": context.cocoon.name,
        },
        "session_state": {
            "relation_score": context.session_state.relation_score,
            "persona": context.session_state.persona_json,
            "active_tags": _serialize_tags(list(context.session_state.active_tags_json or []), context, catalog),
        },
        "visible_messages": [_runtime_message_payload(message, context, catalog) for message in context.visible_messages],
        "memory_context": [_runtime_memory_payload(memory, context, catalog) for memory in context.memory_context],
        "runtime_event": _runtime_event_payload(context),
        "wakeup_context": _sanitize_prompt_value(context.external_context.get("wakeup_context")),
        "pending_wakeups": pending_wakeups,
        "merge_context": _merge_context_payload(context, catalog),
        "provider_capabilities": _sanitize_provider_capabilities(provider_capabilities),
    }


def record_prompt_render_artifacts(
    session: Session,
    audit_service: AuditService,
    audit_run: AuditRun,
    audit_step: AuditStep,
    template: PromptTemplate,
    revision: PromptTemplateRevision,
    snapshot: dict[str, Any],
    rendered_prompt: str,
    *,
    summary_prefix: str,
) -> tuple[str, str]:
    variables_artifact = audit_service.record_json_artifact(
        session,
        audit_run,
        audit_step,
        "prompt_variables",
        {
            "template_id": template.id,
            "template_type": template.template_type,
            "revision_id": revision.id,
            "variables": snapshot,
        },
        summary=f"{summary_prefix} prompt variables snapshot",
    )
    snapshot_artifact = audit_service.record_json_artifact(
        session,
        audit_run,
        audit_step,
        "prompt_snapshot",
        {
            "template_id": template.id,
            "template_type": template.template_type,
            "revision_id": revision.id,
            "rendered_prompt": rendered_prompt,
        },
        summary=f"{summary_prefix} prompt snapshot",
    )
    audit_service.record_link(
        session,
        audit_run,
        "rendered_from",
        source_artifact_id=variables_artifact.id,
        target_artifact_id=snapshot_artifact.id,
    )
    return variables_artifact.id, snapshot_artifact.id
