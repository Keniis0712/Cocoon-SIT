from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditRun, AuditStep, PromptTemplate, PromptTemplateRevision
from app.services.audit.service import AuditService


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
