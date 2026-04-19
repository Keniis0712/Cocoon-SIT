from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import ActionDispatch, AuditRun, MemoryChunk, MemoryTag, Message, MessageTag, SessionState
from app.models.entities import ActionStatus
from app.services.audit.service import AuditService
from app.services.memory.service import MemoryService
from app.services.runtime.types import ContextPackage, GenerationOutput, MetaDecision


class SideEffects:
    """Applies runtime decisions to persisted state, messages, and memory."""

    def __init__(self, audit_service: AuditService, memory_service: MemoryService):
        self.audit_service = audit_service
        self.memory_service = memory_service

    def apply_state_patch(self, session: Session, context: ContextPackage, meta: MetaDecision) -> SessionState:
        state = context.session_state
        state.relation_score += meta.relation_delta
        state.persona_json = state.persona_json | meta.persona_patch
        for op in meta.tag_ops:
            if op.startswith("+"):
                tag = op[1:]
                if tag and tag not in state.active_tags_json:
                    state.active_tags_json = [*state.active_tags_json, tag]
            elif op.startswith("-"):
                tag = op[1:]
                state.active_tags_json = [item for item in state.active_tags_json if item != tag]
        if context.runtime_event.event_type == "merge" and context.external_context.get("source_state"):
            source_state = context.external_context["source_state"]
            merged_persona = dict(source_state.persona_json)
            merged_persona.update(state.persona_json)
            state.persona_json = merged_persona
            state.relation_score = int((state.relation_score + source_state.relation_score) / 2)
            for tag in source_state.active_tags_json:
                if tag not in state.active_tags_json:
                    state.active_tags_json = [*state.active_tags_json, tag]
        session.flush()
        return state

    def build_state_snapshot(self, state: SessionState) -> dict:
        return {
            "relation_score": state.relation_score,
            "persona_json": state.persona_json,
            "active_tags": state.active_tags_json,
            "current_wakeup_task_id": state.current_wakeup_task_id,
        }

    def persist_generated_output(
        self,
        session: Session,
        context: ContextPackage,
        action: ActionDispatch,
        generation: GenerationOutput,
    ) -> tuple[Message, MemoryChunk]:
        event_type = context.runtime_event.event_type
        role = "assistant"
        memory_scope = "dialogue"
        if event_type == "wakeup":
            memory_scope = "system"
        elif event_type == "pull":
            role = "system"
            memory_scope = "pull"
        elif event_type == "merge":
            role = "system"
            memory_scope = "merge"
        message = Message(
            cocoon_id=context.runtime_event.cocoon_id,
            chat_group_id=context.runtime_event.chat_group_id,
            action_id=action.id,
            role=role,
            content=generation.reply_text,
            tags_json=context.session_state.active_tags_json,
        )
        session.add(message)
        session.flush()
        for tag in context.session_state.active_tags_json:
            session.add(MessageTag(message_id=message.id, tag_id=tag))
        memory = MemoryChunk(
            cocoon_id=context.runtime_event.cocoon_id,
            chat_group_id=context.runtime_event.chat_group_id,
            owner_user_id=context.memory_owner_user_id,
            character_id=context.character.id,
            source_message_id=message.id,
            scope=memory_scope,
            content=generation.reply_text,
            summary=generation.reply_text[:200],
            tags_json=context.session_state.active_tags_json,
            meta_json={
                "action_id": action.id,
                "event_type": event_type,
                "target_type": context.target_type,
                "target_id": context.target_id,
            },
        )
        session.add(memory)
        session.flush()
        for tag in context.session_state.active_tags_json:
            session.add(MemoryTag(memory_chunk_id=memory.id, tag_id=tag))
        self.memory_service.index_memory_chunk(
            session,
            memory,
            source_text=memory.summary or memory.content,
            meta_json={
                "action_id": action.id,
                "event_type": event_type,
                "target_type": context.target_type,
                "target_id": context.target_id,
            },
        )
        session.flush()
        return message, memory

    def record_side_effects_result(
        self,
        session: Session,
        audit_run: AuditRun,
        audit_step,
        state: SessionState,
        *,
        action: ActionDispatch,
        message: Message | None = None,
        memory: MemoryChunk | None = None,
        scheduler_result: dict | None = None,
    ) -> None:
        snapshot = self.build_state_snapshot(state) | {
            "action_id": action.id,
            "event_type": action.event_type,
            "target_type": "chat_group" if action.chat_group_id else "cocoon",
            "target_id": action.chat_group_id or action.cocoon_id,
            "final_message_id": message.id if message else None,
            "memory_chunk_id": memory.id if memory else None,
            "scheduler_result": scheduler_result or {},
        }
        self.audit_service.record_json_artifact(
            session,
            audit_run,
            audit_step,
            "side_effects_result",
            snapshot,
            summary="Round side effects result",
            metadata_json={
                "action_id": action.id,
                "event_type": action.event_type,
                "relation_score": state.relation_score,
            },
        )

    def finish_action(
        self,
        session: Session,
        action: ActionDispatch,
        audit_run: AuditRun,
        status: str,
        error_text: str | None = None,
    ) -> None:
        action.status = status
        action.error_text = error_text
        action.finished_at = datetime.now(UTC).replace(tzinfo=None)
        self.audit_service.finish_run(session, audit_run, status)
        session.flush()
