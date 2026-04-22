from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import ActionDispatch, AuditRun, MemoryChunk, MemoryTag, Message, MessageTag, SessionState
from app.models.entities import ActionStatus
from app.models.workspace import DEFAULT_RELATION_SCORE, MAX_RELATION_SCORE, MIN_RELATION_SCORE
from app.services.audit.service import AuditService
from app.services.memory.service import MemoryService
from app.services.runtime.types import ContextPackage, GenerationOutput, MemoryCandidate, MetaDecision


class SideEffects:
    """Applies runtime decisions to persisted state, messages, and memory."""

    def __init__(self, audit_service: AuditService, memory_service: MemoryService):
        self.audit_service = audit_service
        self.memory_service = memory_service

    def apply_state_patch(self, session: Session, context: ContextPackage, meta: MetaDecision) -> SessionState:
        state = context.session_state
        current_score = state.relation_score if state.relation_score is not None else DEFAULT_RELATION_SCORE
        state.relation_score = max(MIN_RELATION_SCORE, min(MAX_RELATION_SCORE, current_score + meta.relation_delta))
        state.persona_json = state.persona_json | meta.persona_patch
        for op in meta.tag_ops:
            if op.action == "add":
                tag = self._resolve_tag_reference(context, op.tag)
                if tag and tag not in state.active_tags_json:
                    state.active_tags_json = [*state.active_tags_json, tag]
            elif op.action == "remove":
                tag = self._resolve_tag_reference(context, op.tag)
                state.active_tags_json = [item for item in state.active_tags_json if item != tag]
        if context.runtime_event.event_type == "merge" and context.external_context.get("source_state"):
            source_state = context.external_context["source_state"]
            merged_persona = dict(source_state.persona_json)
            merged_persona.update(state.persona_json)
            state.persona_json = merged_persona
            merged_score = int((state.relation_score + source_state.relation_score) / 2)
            state.relation_score = max(MIN_RELATION_SCORE, min(MAX_RELATION_SCORE, merged_score))
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

    def persist_generated_message(
        self,
        session: Session,
        context: ContextPackage,
        action: ActionDispatch,
        generation: GenerationOutput,
    ) -> Message:
        event_type = context.runtime_event.event_type
        role = "assistant"
        if event_type == "pull":
            role = "system"
        elif event_type == "merge":
            role = "system"
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
        return message

    def persist_memory_candidates(
        self,
        session: Session,
        context: ContextPackage,
        action: ActionDispatch,
        candidates: list[MemoryCandidate],
        *,
        source_message: Message | None = None,
    ) -> list[MemoryChunk]:
        memories: list[MemoryChunk] = []
        for candidate in candidates:
            summary = candidate.summary.strip()
            content = candidate.content.strip()
            if not summary or not content:
                continue
            tag_ids = self._resolve_candidate_tags(context, candidate) or list(context.session_state.active_tags_json)
            memory = MemoryChunk(
                cocoon_id=context.runtime_event.cocoon_id,
                chat_group_id=context.runtime_event.chat_group_id,
                owner_user_id=candidate.owner_user_id or context.memory_owner_user_id,
                character_id=context.character.id,
                source_message_id=source_message.id if source_message else None,
                scope=candidate.scope,
                content=content,
                summary=summary,
                tags_json=tag_ids,
                meta_json={
                    "action_id": action.id,
                    "event_type": context.runtime_event.event_type,
                    "target_type": context.target_type,
                    "target_id": context.target_id,
                    "source_kind": "runtime_analysis",
                    "importance": candidate.importance,
                },
            )
            session.add(memory)
            session.flush()
            for tag in tag_ids:
                session.add(MemoryTag(memory_chunk_id=memory.id, tag_id=tag))
            self.memory_service.index_memory_chunk(
                session,
                memory,
                source_text=summary,
                meta_json={
                    "action_id": action.id,
                    "event_type": context.runtime_event.event_type,
                    "target_type": context.target_type,
                    "target_id": context.target_id,
                    "source_kind": "runtime_analysis",
                    "importance": candidate.importance,
                },
            )
            memories.append(memory)
        session.flush()
        return memories

    def _resolve_candidate_tags(self, context: ContextPackage, candidate: MemoryCandidate) -> list[str]:
        resolved: list[str] = []
        for tag_ref in candidate.tags:
            tag = self._resolve_tag_reference(context, tag_ref.tag)
            if tag and tag not in resolved:
                resolved.append(tag)
        return resolved

    def _resolve_tag_reference(self, context: ContextPackage, raw_tag: str) -> str:
        tag = raw_tag.strip()
        if not tag:
            return ""
        catalog = context.external_context.get("tag_catalog_by_ref") or {}
        if not isinstance(catalog, dict):
            return tag
        direct = catalog.get(tag)
        if isinstance(direct, dict):
            return str(direct.get("id") or direct.get("tag_id") or tag)
        normalized = tag.casefold()
        for payload in catalog.values():
            if not isinstance(payload, dict):
                continue
            candidates = [
                payload.get("id"),
                payload.get("tag_id"),
                payload.get("meta_json", {}).get("name") if isinstance(payload.get("meta_json"), dict) else None,
                payload.get("meta_json", {}).get("title") if isinstance(payload.get("meta_json"), dict) else None,
                payload.get("meta_json", {}).get("display_name") if isinstance(payload.get("meta_json"), dict) else None,
                payload.get("meta_json", {}).get("label") if isinstance(payload.get("meta_json"), dict) else None,
            ]
            for candidate in candidates:
                if isinstance(candidate, str) and candidate.strip().casefold() == normalized:
                    return str(payload.get("id") or payload.get("tag_id") or tag)
        return tag

    def record_side_effects_result(
        self,
        session: Session,
        audit_run: AuditRun,
        audit_step,
        state: SessionState,
        *,
        action: ActionDispatch,
        message: Message | None = None,
        memories: list[MemoryChunk] | None = None,
        scheduler_result: dict | None = None,
    ) -> None:
        snapshot = self.build_state_snapshot(state) | {
            "action_id": action.id,
            "event_type": action.event_type,
            "target_type": "chat_group" if action.chat_group_id else "cocoon",
            "target_id": action.chat_group_id or action.cocoon_id,
            "final_message_id": message.id if message else None,
            "memory_chunk_ids": [memory.id for memory in memories or []],
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
