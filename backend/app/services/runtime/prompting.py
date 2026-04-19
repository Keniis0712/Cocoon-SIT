from __future__ import annotations

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


def _runtime_message_payload(message, context: ContextPackage, catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tag_refs = list(message.tags_json or [])
    retracted_suffix = "\n\n[system note: this message was later retracted]" if message.is_retracted else ""
    return {
        "role": message.role,
        "content": f"{message.content}{retracted_suffix}",
        "sender_user_id": message.sender_user_id,
        "sender_display_name": message.sender_user_id,
        "is_retracted": message.is_retracted,
        "tags": _serialize_tags(tag_refs, context, catalog),
        "mentionable_in_current_target": _mentionable_for_target(tag_refs, context, catalog),
    }


def _runtime_memory_payload(memory, context: ContextPackage, catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tag_refs = list(memory.tags_json or [])
    return {
        "scope": memory.scope,
        "summary": memory.summary,
        "content": memory.content,
        "owner_user_id": memory.owner_user_id,
        "character_id": memory.character_id,
        "tags": _serialize_tags(tag_refs, context, catalog),
        "mentionable_in_current_target": _mentionable_for_target(tag_refs, context, catalog),
        "source_target_type": "chat_group" if memory.chat_group_id else "cocoon",
        "source_target_id": memory.chat_group_id or memory.cocoon_id,
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
        **payload,
        "source_state": {
            "relation_score": source_state_payload.get("relation_score", 0),
            "persona_json": source_state_payload.get("persona_json", {}),
            "active_tags": _serialize_tags(tag_refs, context, catalog),
        },
    }


def build_runtime_prompt_variables(
    context: ContextPackage,
    *,
    provider_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = _tag_catalog(context)
    return {
        "character_settings": context.character.settings_json
        | {"prompt_summary": context.character.prompt_summary},
        "conversation_target": {
            "type": context.target_type,
            "id": context.target_id,
            "name": context.cocoon.name,
        },
        "session_state": {
            "relation_score": context.session_state.relation_score,
            "persona": context.session_state.persona_json,
            "active_tags": _serialize_tags(list(context.session_state.active_tags_json or []), context, catalog),
            "pending_wakeups": context.external_context.get("pending_wakeups", []),
        },
        "visible_messages": [_runtime_message_payload(message, context, catalog) for message in context.visible_messages],
        "memory_context": [_runtime_memory_payload(memory, context, catalog) for memory in context.memory_context],
        "runtime_event": {
            "event_type": context.runtime_event.event_type,
            "target_type": context.runtime_event.target_type,
            "target_id": context.runtime_event.target_id,
            **context.runtime_event.payload,
        },
        "wakeup_context": context.external_context.get("wakeup_context"),
        "pending_wakeups": context.external_context.get("pending_wakeups", []),
        "merge_context": _merge_context_payload(context, catalog),
        "provider_capabilities": provider_capabilities or {},
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
