from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditRun, AuditStep, PromptTemplate, PromptTemplateRevision
from app.services.audit.service import AuditService
from app.services.runtime.types import ContextPackage


def _tag_visibility_map(context: ContextPackage) -> dict[str, str]:
    payload = context.external_context.get("tag_visibility_by_ref") or {}
    return payload if isinstance(payload, dict) else {}


def _mentionable_for_target(tag_refs: list[str], context: ContextPackage, visibility_map: dict[str, str]) -> bool:
    if not tag_refs:
        return True
    allowed = {"public"} if context.target_type == "chat_group" else {"public", "group_private"}
    for tag_ref in tag_refs:
        visibility = visibility_map.get(tag_ref, "private")
        if visibility not in allowed:
            return False
    return True


def _runtime_message_payload(message, context: ContextPackage, visibility_map: dict[str, str]) -> dict[str, Any]:
    tag_refs = list(message.tags_json or [])
    retracted_suffix = "\n\n[system note: this message was later retracted]" if message.is_retracted else ""
    return {
        "role": message.role,
        "content": f"{message.content}{retracted_suffix}",
        "sender_user_id": message.sender_user_id,
        "sender_display_name": message.sender_user_id,
        "is_retracted": message.is_retracted,
        "tag_refs": tag_refs,
        "tag_visibility": {tag_ref: visibility_map.get(tag_ref, "private") for tag_ref in tag_refs},
        "mentionable_in_current_target": _mentionable_for_target(tag_refs, context, visibility_map),
    }


def _runtime_memory_payload(memory, context: ContextPackage, visibility_map: dict[str, str]) -> dict[str, Any]:
    tag_refs = list(memory.tags_json or [])
    return {
        "scope": memory.scope,
        "summary": memory.summary,
        "content": memory.content,
        "owner_user_id": memory.owner_user_id,
        "character_id": memory.character_id,
        "tag_refs": tag_refs,
        "tag_visibility": {tag_ref: visibility_map.get(tag_ref, "private") for tag_ref in tag_refs},
        "mentionable_in_current_target": _mentionable_for_target(tag_refs, context, visibility_map),
        "source_target_type": "chat_group" if memory.chat_group_id else "cocoon",
        "source_target_id": memory.chat_group_id or memory.cocoon_id,
    }


def build_runtime_prompt_variables(
    context: ContextPackage,
    *,
    provider_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    visibility_map = _tag_visibility_map(context)
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
            "active_tags": context.session_state.active_tags_json,
            "pending_wakeups": context.external_context.get("pending_wakeups", []),
        },
        "visible_messages": [_runtime_message_payload(message, context, visibility_map) for message in context.visible_messages],
        "memory_context": [_runtime_memory_payload(memory, context, visibility_map) for memory in context.memory_context],
        "runtime_event": {
            "event_type": context.runtime_event.event_type,
            "target_type": context.runtime_event.target_type,
            "target_id": context.runtime_event.target_id,
            **context.runtime_event.payload,
        },
        "wakeup_context": context.external_context.get("wakeup_context"),
        "pending_wakeups": context.external_context.get("pending_wakeups", []),
        "merge_context": context.external_context.get("merge_context"),
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
