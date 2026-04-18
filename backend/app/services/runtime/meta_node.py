"""Runtime meta-decision service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.audit.service import AuditService
from app.services.prompts.service import PromptTemplateService
from app.services.runtime.meta.wakeup_command_parser import WakeupCommandParser
from app.services.runtime.prompting import build_runtime_prompt_variables, record_prompt_render_artifacts
from app.services.runtime.types import ContextPackage, MetaDecision


class MetaNode:
    """Evaluates context and decides whether the runtime should reply or stay silent."""

    def __init__(
        self,
        prompt_service: PromptTemplateService,
        audit_service: AuditService,
        wakeup_command_parser: WakeupCommandParser | None = None,
    ) -> None:
        self.prompt_service = prompt_service
        self.audit_service = audit_service
        self.wakeup_command_parser = wakeup_command_parser or WakeupCommandParser()

    def evaluate(
        self,
        session: Session,
        context: ContextPackage,
        audit_run,
        audit_step,
    ) -> MetaDecision:
        template, revision, snapshot, rendered_prompt = self.prompt_service.render(
            session=session,
            template_type="meta",
            variables=build_runtime_prompt_variables(context),
        )
        record_prompt_render_artifacts(
            session,
            self.audit_service,
            audit_run,
            audit_step,
            template,
            revision,
            snapshot,
            rendered_prompt,
            summary_prefix="meta",
        )

        event_type = context.runtime_event.event_type
        if event_type == "wakeup":
            reason = str(context.runtime_event.payload.get("reason") or "scheduled wakeup")
            return MetaDecision(
                decision="reply",
                relation_delta=0,
                persona_patch={"last_wakeup_reason": reason[:120]},
                tag_ops=[],
                internal_thought="Wake up and continue the cocoon conversation proactively.",
                next_wakeup_hint=None,
            )
        if event_type == "pull":
            return MetaDecision(
                decision="reply",
                relation_delta=0,
                persona_patch={"last_pull_source": context.runtime_event.payload.get("source_cocoon_id")},
                tag_ops=[],
                internal_thought="Summarize relevant knowledge from the source cocoon into the target cocoon.",
                next_wakeup_hint=None,
            )
        if event_type == "merge":
            return MetaDecision(
                decision="reply",
                relation_delta=0,
                persona_patch={"last_merge_source": context.runtime_event.payload.get("source_cocoon_id")},
                tag_ops=[],
                internal_thought="Reconcile source branch state and summarize the merge into the target cocoon.",
                next_wakeup_hint=None,
            )

        latest_user = next(
            (message for message in reversed(context.visible_messages) if message.role == "user"),
            None,
        )
        latest_content = latest_user.content if latest_user else ""
        next_wakeup_hint = self.wakeup_command_parser.parse(latest_content)
        decision = "silence" if latest_content.strip().startswith("/silent") else "reply"
        persona_patch = {"last_seen_intent": latest_content[:120]}
        internal_thought = (
            "Respond helpfully while preserving the cocoon persona. "
            f"Meta prompt size={len(rendered_prompt)}"
        )
        return MetaDecision(
            decision=decision,
            relation_delta=1 if latest_content else 0,
            persona_patch=persona_patch,
            tag_ops=[],
            internal_thought=internal_thought,
            next_wakeup_hint=next_wakeup_hint,
        )
