from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ActionDispatch
from app.models.entities import ActionStatus
from app.services.runtime.context_builder import ContextBuilder
from app.services.runtime.generator_node import GeneratorNode
from app.services.runtime.meta_node import MetaNode
from app.services.runtime.reply_delivery_service import ReplyDeliveryService
from app.services.runtime.round_preparation_service import RoundPreparationService
from app.services.runtime.scheduler_node import SchedulerNode
from app.services.runtime.side_effects import SideEffects
from app.services.runtime.state_patch_service import StatePatchService
from app.services.audit.service import AuditService


class ChatRuntime:
    """Top-level orchestrator for one runtime round."""

    def __init__(
        self,
        context_builder: ContextBuilder,
        meta_node: MetaNode,
        generator_node: GeneratorNode,
        scheduler_node: SchedulerNode,
        round_preparation_service: RoundPreparationService,
        state_patch_service: StatePatchService,
        reply_delivery_service: ReplyDeliveryService,
        side_effects: SideEffects,
        audit_service: AuditService,
    ) -> None:
        self.context_builder = context_builder
        self.meta_node = meta_node
        self.generator_node = generator_node
        self.scheduler_node = scheduler_node
        self.round_preparation_service = round_preparation_service
        self.state_patch_service = state_patch_service
        self.reply_delivery_service = reply_delivery_service
        self.side_effects = side_effects
        self.audit_service = audit_service

    def run(self, session: Session, action: ActionDispatch) -> None:
        event, audit_run = self.round_preparation_service.prepare(session, action)
        context_step = self.audit_service.start_step(session, audit_run, "context_builder")
        context = self.context_builder.build(session, event)
        self.audit_service.record_json_artifact(
            session,
            audit_run,
            context_step,
            "memory_retrieval",
            {"hits": [hit.to_artifact_payload() for hit in context.memory_hits]},
            summary="Retrieved memory context",
            metadata_json={"hit_count": len(context.memory_hits)},
        )
        self.audit_service.finish_step(session, context_step, ActionStatus.completed)

        meta_step = self.audit_service.start_step(session, audit_run, "meta_node")
        meta = self.meta_node.evaluate(session, context, audit_run, meta_step)
        self.audit_service.record_json_artifact(
            session,
            audit_run,
            meta_step,
            "meta_output",
            {
                "decision": meta.decision,
                "relation_delta": meta.relation_delta,
                "persona_patch": meta.persona_patch,
                "tag_ops": meta.tag_ops,
                "internal_thought": meta.internal_thought,
                "next_wakeup_hint": meta.next_wakeup_hint,
            },
        )
        self.state_patch_service.apply_and_publish(
            session,
            context,
            meta,
            action_id=action.id,
        )
        self.audit_service.finish_step(session, meta_step, ActionStatus.completed)

        scheduler_step = self.audit_service.start_step(session, audit_run, "scheduler_node")
        scheduler_result = self.scheduler_node.schedule(session, context, meta)
        self.audit_service.record_json_artifact(
            session,
            audit_run,
            scheduler_step,
            "workflow_summary",
            scheduler_result,
            summary="Scheduler result",
            metadata_json=scheduler_result,
        )
        self.audit_service.finish_step(session, scheduler_step, ActionStatus.completed)

        message = None
        memory = None
        if meta.decision != "silence":
            generator_step = self.audit_service.start_step(session, audit_run, "generator_node")
            generation = self.generator_node.generate(session, context, audit_run, generator_step)
            message, memory = self.reply_delivery_service.deliver(
                session,
                context,
                action,
                audit_run,
                generator_step,
                generation,
            )
            self.audit_service.finish_step(session, generator_step, ActionStatus.completed)

        side_effects_step = self.audit_service.start_step(session, audit_run, "side_effects")
        self.side_effects.record_side_effects_result(
            session,
            audit_run,
            side_effects_step,
            context.session_state,
            action=action,
            message=message,
            memory=memory,
            scheduler_result=scheduler_result,
        )
        if meta.decision != "silence":
            self.state_patch_service.publish_snapshot(
                context.cocoon.id,
                context.session_state,
                action_id=action.id,
            )
        self.audit_service.finish_step(session, side_effects_step, ActionStatus.completed)
        self.side_effects.finish_action(session, action, audit_run, ActionStatus.completed)
