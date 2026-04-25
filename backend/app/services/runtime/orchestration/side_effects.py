from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import ActionDispatch, AuditRun, MemoryChunk, MemoryTag, Message, MessageTag, SessionState, User
from app.models.entities import ActionStatus
from app.models.workspace import DEFAULT_RELATION_SCORE, MAX_RELATION_SCORE, MIN_RELATION_SCORE
from app.services.audit.service import AuditService
from app.services.catalog.tag_policy import canonicalize_tag_refs, ensure_state_default_tag
from app.services.memory.service import MemoryService
from app.services.runtime.types import ContextPackage, GenerationOutput, MemoryCandidate, MetaDecision


class SideEffects:
    """Applies runtime decisions to persisted state, messages, and memory."""

    def __init__(self, audit_service: AuditService, memory_service: MemoryService):
        self.audit_service = audit_service
        self.memory_service = memory_service

    def apply_state_patch(self, session: Session, context: ContextPackage, meta: MetaDecision) -> SessionState:
        state = context.session_state
        if isinstance(state, SessionState):
            state = ensure_state_default_tag(session, state)
        current_score = state.relation_score if state.relation_score is not None else DEFAULT_RELATION_SCORE
        state.relation_score = max(MIN_RELATION_SCORE, min(MAX_RELATION_SCORE, current_score + meta.relation_delta))
        state.persona_json = state.persona_json | meta.persona_patch
        for op in meta.tag_ops:
            if op.action == "add":
                tag = self._resolve_tag_index(context, op.tag_index)
                if tag and tag not in state.active_tags_json:
                    state.active_tags_json = canonicalize_tag_refs(
                        session,
                        [*state.active_tags_json, tag],
                        include_default=True,
                    )
            elif op.action == "remove":
                tag = self._resolve_tag_index(context, op.tag_index)
                state.active_tags_json = canonicalize_tag_refs(
                    session,
                    [item for item in state.active_tags_json if item != tag],
                    include_default=True,
                )
        if context.runtime_event.event_type == "merge" and context.external_context.get("source_state"):
            source_state = context.external_context["source_state"]
            merged_persona = dict(source_state.persona_json)
            merged_persona.update(state.persona_json)
            state.persona_json = merged_persona
            merged_score = int((state.relation_score + source_state.relation_score) / 2)
            state.relation_score = max(MIN_RELATION_SCORE, min(MAX_RELATION_SCORE, merged_score))
            for tag in source_state.active_tags_json:
                if tag not in state.active_tags_json:
                    state.active_tags_json = canonicalize_tag_refs(
                        session,
                        [*state.active_tags_json, tag],
                        include_default=True,
                    )
        session.flush()
        return state

    def build_state_snapshot(self, state: SessionState) -> dict:
        return {
            "relation_score": state.relation_score,
            "persona_json": state.persona_json,
            "active_tags": state.active_tags_json,
            "current_wakeup_task_id": state.current_wakeup_task_id,
        }

    def persist_thought_message(
        self,
        session: Session,
        context: ContextPackage,
        action: ActionDispatch,
        meta: MetaDecision,
    ) -> Message:
        thought_text = str(meta.internal_thought or "").strip() or "Structured meta decision completed."
        event_summary = str(meta.event_summary or "").strip() or None
        return self._persist_message(
            session,
            context=context,
            action=action,
            role="assistant",
            content=thought_text,
            is_thought=True,
            retraction_note=event_summary,
        )

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
        return self._persist_message(
            session,
            context=context,
            action=action,
            role=role,
            content=generation.reply_text,
        )

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
            owner_user_id = self._resolve_memory_owner_user_id(session, context, candidate)
            memory = MemoryChunk(
                cocoon_id=context.runtime_event.cocoon_id,
                chat_group_id=context.runtime_event.chat_group_id,
                owner_user_id=owner_user_id,
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
                meta_json=memory.meta_json,
            )
            memories.append(memory)
        session.flush()
        return memories

    def _resolve_memory_owner_user_id(
        self,
        session: Session,
        context: ContextPackage,
        candidate: MemoryCandidate,
    ) -> str | None:
        for raw_value in (context.memory_owner_user_id, candidate.owner_user_id):
            normalized = str(raw_value or "").strip()
            if not normalized:
                continue
            if session.get(User, normalized):
                return normalized
        return None

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
            meta = payload.get("meta_json") if isinstance(payload.get("meta_json"), dict) else {}
            for candidate in (
                payload.get("id"),
                payload.get("tag_id"),
                payload.get("brief"),
                meta.get("name"),
            ):
                if isinstance(candidate, str) and candidate.strip().casefold() == normalized:
                    return str(payload.get("id") or payload.get("tag_id") or tag)
        return tag

    def _resolve_tag_index(self, context: ContextPackage, tag_index: int) -> str:
        catalog = context.external_context.get("prompt_tag_catalog_by_index") or {}
        if not isinstance(catalog, dict):
            return ""
        payload = catalog.get(int(tag_index))
        if not isinstance(payload, dict):
            return ""
        tag_id = payload.get("id")
        return str(tag_id).strip() if isinstance(tag_id, str) else ""

    def record_side_effects_result(
        self,
        session: Session,
        audit_run: AuditRun,
        audit_step,
        state: SessionState,
        *,
        action: ActionDispatch,
        message: Message | None = None,
        thought_message: Message | None = None,
        memories: list[MemoryChunk] | None = None,
        scheduler_result: dict | None = None,
    ) -> None:
        snapshot = self.build_state_snapshot(state) | {
            "action_id": action.id,
            "event_type": action.event_type,
            "target_type": "chat_group" if action.chat_group_id else "cocoon",
            "target_id": action.chat_group_id or action.cocoon_id,
            "final_message_id": message.id if message else None,
            "thought_message_id": thought_message.id if thought_message else None,
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

    def _persist_message(
        self,
        session: Session,
        *,
        context: ContextPackage,
        action: ActionDispatch,
        role: str,
        content: str,
        is_thought: bool = False,
        retraction_note: str | None = None,
    ) -> Message:
        message = Message(
            cocoon_id=context.runtime_event.cocoon_id,
            chat_group_id=context.runtime_event.chat_group_id,
            action_id=action.id,
            role=role,
            content=content,
            is_thought=is_thought,
            retraction_note=retraction_note,
            tags_json=context.session_state.active_tags_json,
        )
        session.add(message)
        session.flush()
        for tag in context.session_state.active_tags_json:
            session.add(MessageTag(message_id=message.id, tag_id=tag))
        return message
