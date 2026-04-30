from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import (
    ActionDispatch,
    AuditRun,
    MemoryChunk,
    MemoryTag,
    Message,
    MessageTag,
    SessionState,
    User,
)
from app.models.entities import ActionStatus
from app.models.workspace import DEFAULT_RELATION_SCORE, MAX_RELATION_SCORE, MIN_RELATION_SCORE
from app.services.audit.service import AuditService
from app.services.catalog.tag_policy import canonicalize_tag_refs, ensure_state_default_tag
from app.services.memory.service import MemoryService
from app.services.runtime.errors import RuntimeActionAbortedError
from app.services.runtime.types import (
    ContextPackage,
    GenerationOutput,
    MemoryCandidate,
    MemoryOperation,
    MetaDecision,
)
from app.services.workspace.targets import ensure_target_task_state


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
        session_update = meta.session_update or {}
        if isinstance(session_update.get("persona_patch"), dict):
            state.persona_json = state.persona_json | dict(session_update["persona_patch"])
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
        self.ensure_action_is_writable(session, action)
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
        self.ensure_action_is_writable(session, action)
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
        return self.persist_memory_ops(
            session,
            context,
            action,
            [
                MemoryOperation(
                    op="candidate" if int(candidate.importance or 0) < 3 else "upsert",
                    content=candidate.content,
                    summary=candidate.summary,
                    memory_type=candidate.memory_type,
                    memory_pool=candidate.memory_pool,
                    tags=candidate.tags,
                    importance=candidate.importance,
                    confidence=candidate.confidence,
                    valid_until=candidate.valid_until,
                    reason=candidate.reason,
                )
                for candidate in candidates
            ],
            source_message=source_message,
        )

    def apply_task_state_patch(
        self,
        session: Session,
        context: ContextPackage,
        meta: MetaDecision,
    ):
        payload = meta.task_state_update or {}
        if not payload:
            return context.task_state
        state = context.task_state or ensure_target_task_state(
            session,
            cocoon_id=context.runtime_event.cocoon_id,
            chat_group_id=context.runtime_event.chat_group_id,
        )
        for field, value in (
            ("task_name", payload.get("task_name")),
            ("goal", payload.get("goal")),
            ("progress", payload.get("progress")),
            ("status", payload.get("status")),
        ):
            if value is not None:
                setattr(state, field, value)
        if isinstance(payload.get("meta_json"), dict):
            state.meta_json = dict(state.meta_json or {}) | dict(payload["meta_json"])
        if payload.get("completed"):
            state.completed_at = datetime.now(UTC).replace(tzinfo=None)
            state.status = "completed"
        expires_at = self._parse_timestamp(payload.get("expires_at"))
        if expires_at is not None:
            state.expires_at = expires_at
        session.flush()
        context.task_state = state
        return state

    def apply_fact_cache_ops(
        self,
        session: Session,
        context: ContextPackage,
        meta: MetaDecision,
    ) -> list[str]:
        applied: list[str] = []
        for op in meta.fact_cache_ops:
            if op.op == "delete":
                self.memory_service.delete_fact_cache_entry(
                    session,
                    cache_key=op.cache_key,
                    cocoon_id=context.runtime_event.cocoon_id,
                    chat_group_id=context.runtime_event.chat_group_id,
                )
                applied.append(op.cache_key)
                continue
            self.memory_service.upsert_fact_cache_entry(
                session,
                cache_key=op.cache_key,
                content=op.content,
                summary=op.summary,
                valid_until=self._parse_timestamp(op.valid_until),
                meta_json=op.meta_json,
                cocoon_id=context.runtime_event.cocoon_id,
                chat_group_id=context.runtime_event.chat_group_id,
            )
            applied.append(op.cache_key)
        return applied

    def persist_memory_ops(
        self,
        session: Session,
        context: ContextPackage,
        action: ActionDispatch,
        ops: list[MemoryOperation],
        *,
        source_message: Message | None = None,
    ) -> list[MemoryChunk]:
        created_or_updated: list[MemoryChunk] = []
        profile = context.memory_profile or {}
        candidate_promote_hits = int(profile.get("candidate_promote_hits") or 2)
        candidate_ttl_hours = int(profile.get("candidate_ttl_hours") or 72)
        for op in ops:
            if op.op == "archive":
                if op.target_memory_id:
                    memory = session.get(MemoryChunk, op.target_memory_id)
                    if memory:
                        memory.status = "archived"
                        created_or_updated.append(memory)
                for memory_id in op.supersedes_memory_ids:
                    memory = session.get(MemoryChunk, memory_id)
                    if memory:
                        memory.status = "archived"
                continue
            content = str(op.content or "").strip()
            summary = str(op.summary or "").strip() or None
            if op.op != "archive" and not content:
                continue
            tag_ids = self._resolve_memory_op_tags(context, op) or list(context.session_state.active_tags_json)
            owner_user_id = self._resolve_memory_owner_user_id(session, context, None)
            memory_pool = self._normalize_memory_pool(context, op.memory_pool)
            if op.op == "candidate" or int(op.importance or 0) < 3:
                candidate = self.memory_service.upsert_candidate(
                    session,
                    cocoon_id=context.runtime_event.cocoon_id,
                    chat_group_id=context.runtime_event.chat_group_id,
                    owner_user_id=owner_user_id,
                    character_id=context.character.id,
                    memory_pool=memory_pool,
                    memory_type=op.memory_type,
                    summary=summary,
                    content=content,
                    tags_json=tag_ids,
                    importance=max(0, min(2, int(op.importance or 2))),
                    confidence=max(1, min(5, int(op.confidence or 2))),
                    ttl_hours=candidate_ttl_hours,
                    meta_json={
                        "action_id": action.id,
                        "reason": op.reason,
                        "source_kind": "runtime_analysis",
                    },
                )
                if int(candidate.hit_count or 0) >= candidate_promote_hits:
                    created_or_updated.append(
                        self.memory_service.promote_candidate_to_memory(
                            session,
                            candidate,
                            source_kind="candidate_promotion",
                        )
                    )
                continue
            memory = None
            if op.op == "update" and op.target_memory_id:
                memory = session.get(MemoryChunk, op.target_memory_id)
            if memory is None:
                memory = MemoryChunk(
                    cocoon_id=context.runtime_event.cocoon_id,
                    chat_group_id=context.runtime_event.chat_group_id,
                    owner_user_id=owner_user_id,
                    character_id=context.character.id,
                    source_message_id=source_message.id if source_message else None,
                    memory_pool=memory_pool,
                    memory_type=op.memory_type,
                    scope="memory",
                    content=content,
                    summary=summary,
                    tags_json=tag_ids,
                    importance=max(3, min(5, int(op.importance or 3))),
                    confidence=max(1, min(5, int(op.confidence or 3))),
                    status="active",
                    valid_until=self._parse_timestamp(op.valid_until),
                    last_accessed_at=None,
                    access_count=0,
                    source_kind="runtime_analysis",
                    meta_json={},
                )
                session.add(memory)
                session.flush()
            else:
                memory.content = content
                memory.summary = summary
                memory.tags_json = tag_ids
                memory.importance = max(3, min(5, int(op.importance or memory.importance or 3)))
                memory.confidence = max(1, min(5, int(op.confidence or memory.confidence or 3)))
                memory.memory_type = op.memory_type
                memory.memory_pool = memory_pool
                memory.status = "active"
                memory.valid_until = self._parse_timestamp(op.valid_until)
                session.query(MemoryTag).filter(MemoryTag.memory_chunk_id == memory.id).delete()
            memory.meta_json = {
                **dict(memory.meta_json or {}),
                "action_id": action.id,
                "event_type": context.runtime_event.event_type,
                "target_type": context.target_type,
                "target_id": context.target_id,
                "source_kind": memory.source_kind,
                "reason": op.reason,
            }
            session.flush()
            for tag in tag_ids:
                session.add(MemoryTag(memory_chunk_id=memory.id, tag_id=tag))
            self.memory_service.index_memory_chunk(
                session,
                memory,
                source_text=summary or content,
                meta_json=memory.meta_json,
            )
            for memory_id in op.supersedes_memory_ids:
                superseded = session.get(MemoryChunk, memory_id)
                if superseded:
                    superseded.status = "contradicted"
            created_or_updated.append(memory)
        session.flush()
        return created_or_updated

    def _resolve_memory_owner_user_id(
        self,
        session: Session,
        context: ContextPackage,
        candidate: MemoryCandidate | None,
    ) -> str | None:
        candidate_owner = candidate.owner_user_id if candidate is not None else None
        for raw_value in (context.memory_owner_user_id, candidate_owner):
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

    def _resolve_memory_op_tags(self, context: ContextPackage, op: MemoryOperation) -> list[str]:
        resolved: list[str] = []
        for tag_ref in op.tags:
            tag = self._resolve_tag_reference(context, tag_ref.tag)
            if tag and tag not in resolved:
                resolved.append(tag)
        return resolved

    def _normalize_memory_pool(self, context: ContextPackage, raw_pool: str | None) -> str:
        value = str(raw_pool or "").strip()
        if value in {"tree_private", "user_global", "room_local"}:
            return value
        if value == "public":
            return "user_global"
        if context.target_type == "chat_group":
            return "room_local"
        return "tree_private"

    def _parse_timestamp(self, raw_value) -> datetime | None:
        value = str(raw_value or "").strip()
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

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
            "used_memory_ids": list(action.payload_json.get("used_memory_ids", []))
            if isinstance(action.payload_json, dict)
            else [],
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
        session.refresh(action)
        if action.status != ActionStatus.running:
            return
        action.status = status
        action.error_text = error_text
        action.finished_at = datetime.now(UTC).replace(tzinfo=None)
        self.audit_service.finish_run(session, audit_run, status)
        session.flush()

    def ensure_action_is_writable(self, session: Session, action: ActionDispatch) -> None:
        session.refresh(action)
        if action.status != ActionStatus.running:
            raise RuntimeActionAbortedError(
                f"Action {action.id} is no longer writable: status={action.status}"
            )

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
