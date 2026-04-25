from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session
from typing_extensions import TypedDict

from app.models import ActionDispatch, Message
from app.models.entities import ActionStatus
from app.services.audit.service import AuditService
from app.services.runtime.context.builder import ContextBuilder
from app.services.runtime.generation.generator_node import GeneratorNode
from app.services.runtime.meta.node import MetaNode
from app.services.runtime.orchestration.reply_delivery_service import ReplyDeliveryService
from app.services.runtime.orchestration.round_preparation_service import RoundPreparationService
from app.services.runtime.orchestration.side_effects import SideEffects
from app.services.runtime.orchestration.state_patch_service import StatePatchService
from app.services.runtime.scheduling.scheduler_node import SchedulerNode
from app.services.runtime.types import ContextPackage, GenerationOutput, MetaDecision


class RuntimeGraphState(TypedDict, total=False):
    session: Session
    action: ActionDispatch
    audit_run: Any
    event: Any
    context: ContextPackage
    meta: MetaDecision
    scheduler_result: dict[str, Any]
    generation: GenerationOutput
    message: Message | None


class ChatRuntime:
    """Top-level orchestrator for one runtime round."""

    logger = logging.getLogger(__name__)

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
        self.graph = self._build_graph()

    def run(self, session: Session, action: ActionDispatch) -> None:
        self.logger.info(
            "ChatRuntime starting action_id=%s event_type=%s cocoon_id=%s chat_group_id=%s",
            action.id,
            getattr(action, "event_type", None),
            getattr(action, "cocoon_id", None),
            getattr(action, "chat_group_id", None),
        )
        event, audit_run = self.round_preparation_service.prepare(session, action)
        self.graph.invoke(
            {
                "session": session,
                "action": action,
                "event": event,
                "audit_run": audit_run,
                "message": None,
            }
        )
        self.logger.info(
            "ChatRuntime finished action_id=%s event_type=%s audit_run_id=%s",
            action.id,
            getattr(action, "event_type", None),
            getattr(audit_run, "id", None),
        )

    def _build_graph(self):
        graph = StateGraph(RuntimeGraphState)
        graph.add_node("context_builder", self._run_context_builder)
        graph.add_node("meta_node", self._run_meta_node)
        graph.add_node("scheduler_node", self._run_scheduler_node)
        graph.add_node("generator_node", self._run_generator_node)
        graph.add_node("side_effects", self._run_side_effects_node)
        graph.add_edge(START, "context_builder")
        graph.add_edge("context_builder", "meta_node")
        graph.add_edge("meta_node", "scheduler_node")
        graph.add_conditional_edges(
            "scheduler_node",
            self._route_after_scheduler,
            {
                "generator_node": "generator_node",
                "side_effects": "side_effects",
            },
        )
        graph.add_conditional_edges(
            "generator_node",
            self._route_after_generator,
            {
                "side_effects": "side_effects",
            },
        )
        graph.add_edge("side_effects", END)
        return graph.compile()

    def _run_context_builder(self, state: RuntimeGraphState) -> RuntimeGraphState:
        session = state["session"]
        audit_run = state["audit_run"]
        event = state["event"]
        context_step = self.audit_service.start_step(session, audit_run, "context_builder")
        context = self.context_builder.build(session, event)
        self.logger.info(
            "Context built action_id=%s target_type=%s visible_messages=%s memory_hits=%s",
            state["action"].id,
            context.target_type,
            len(context.visible_messages),
            len(context.memory_hits),
        )
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
        return {"context": context}

    def _run_meta_node(self, state: RuntimeGraphState) -> RuntimeGraphState:
        session = state["session"]
        audit_run = state["audit_run"]
        context = state["context"]
        meta_step = self.audit_service.start_step(session, audit_run, "meta_node")
        meta = self.meta_node.evaluate(session, context, audit_run, meta_step)
        self.logger.info(
            "Meta decision action_id=%s decision=%s relation_delta=%s wakeups=%s cancelled_wakeups=%s tag_ops=%s",
            state["action"].id,
            meta.decision,
            meta.relation_delta,
            len(meta.next_wakeup_hints),
            len(meta.cancel_wakeup_task_ids),
            len(meta.tag_ops),
        )
        self.audit_service.record_json_artifact(
            session,
            audit_run,
            meta_step,
            "meta_output",
            {
                "decision": meta.decision,
                "relation_delta": meta.relation_delta,
                "persona_patch": meta.persona_patch,
                "tag_ops": [{"action": op.action, "tag_index": op.tag_index} for op in meta.tag_ops],
                "internal_thought": meta.internal_thought,
                "next_wakeup_hints": meta.next_wakeup_hints,
                "cancel_wakeup_task_ids": meta.cancel_wakeup_task_ids,
                "generation_brief": meta.generation_brief,
            },
        )
        self.audit_service.finish_step(session, meta_step, ActionStatus.completed)
        return {"meta": meta}

    def _run_scheduler_node(self, state: RuntimeGraphState) -> RuntimeGraphState:
        session = state["session"]
        action = state["action"]
        audit_run = state["audit_run"]
        context = state["context"]
        meta = state["meta"]
        self.state_patch_service.apply_and_publish(
            session,
            context,
            meta,
            action_id=action.id,
        )
        scheduler_step = self.audit_service.start_step(session, audit_run, "scheduler_node")
        scheduler_result = self.scheduler_node.schedule(session, context, meta)
        self.logger.info(
            "Scheduler result action_id=%s result=%s",
            action.id,
            scheduler_result,
        )
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
        return {"scheduler_result": scheduler_result}

    def _run_generator_node(self, state: RuntimeGraphState) -> RuntimeGraphState:
        session = state["session"]
        action = state["action"]
        audit_run = state["audit_run"]
        context = state["context"]
        meta = state["meta"]
        generator_step = self.audit_service.start_step(session, audit_run, "generator_node")
        generation = self.generator_node.generate(session, context, meta, audit_run, generator_step)
        self.logger.info(
            "Generator produced reply action_id=%s reply_length=%s provider_kind=%s model_name=%s",
            action.id,
            len(generation.reply_text),
            generation.provider_kind,
            generation.model_name,
        )
        message = self.reply_delivery_service.deliver(
            session,
            context,
            action,
            audit_run,
            generator_step,
            generation,
        )
        self.audit_service.finish_step(session, generator_step, ActionStatus.completed)
        return {"generation": generation, "message": message}

    def _run_side_effects_node(self, state: RuntimeGraphState) -> RuntimeGraphState:
        session = state["session"]
        action = state["action"]
        audit_run = state["audit_run"]
        context = state["context"]
        side_effects_step = self.audit_service.start_step(session, audit_run, "side_effects")
        self.side_effects.record_side_effects_result(
            session,
            audit_run,
            side_effects_step,
            context.session_state,
            action=action,
            message=state.get("message"),
            scheduler_result=state.get("scheduler_result"),
        )
        self.state_patch_service.publish_snapshot(
            action_id=action.id,
            state=context.session_state,
            cocoon_id=context.runtime_event.cocoon_id,
            chat_group_id=context.runtime_event.chat_group_id,
        )
        self.audit_service.finish_step(session, side_effects_step, ActionStatus.completed)
        self.side_effects.finish_action(session, action, audit_run, ActionStatus.completed)
        self.logger.info(
            "Side effects finished action_id=%s final_message_id=%s",
            action.id,
            getattr(state.get("message"), "id", None),
        )
        return {}

    def _route_after_scheduler(self, state: RuntimeGraphState) -> str:
        meta = state["meta"]
        action = state.get("action")
        action_id = getattr(action, "id", None)
        if meta.decision != "silence":
            self.logger.info("Routing to generator action_id=%s", action_id)
            return "generator_node"
        self.logger.info("Skipping generator for action_id=%s because decision=%s", action_id, meta.decision)
        return "side_effects"

    def _route_after_generator(self, state: RuntimeGraphState) -> str:
        return "side_effects"
