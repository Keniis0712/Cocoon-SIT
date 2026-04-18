from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditRun, AuditStep, PromptTemplate, PromptTemplateRevision
from app.services.audit.service import AuditService
from app.services.runtime.types import ContextPackage


def build_runtime_prompt_variables(
    context: ContextPackage,
    *,
    provider_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "character_settings": context.character.settings_json
        | {"prompt_summary": context.character.prompt_summary},
        "session_state": {
            "relation_score": context.session_state.relation_score,
            "persona": context.session_state.persona_json,
            "active_tags": context.session_state.active_tags_json,
        },
        "visible_messages": [
            {"role": message.role, "content": message.content}
            for message in context.visible_messages
        ],
        "memory_context": [
            {"scope": memory.scope, "summary": memory.summary, "content": memory.content}
            for memory in context.memory_context
        ],
        "runtime_event": context.runtime_event.payload,
        "wakeup_context": context.external_context.get("wakeup_context"),
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
