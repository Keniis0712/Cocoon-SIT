"""Memory compaction durable job execution service."""

from __future__ import annotations

import json
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cocoon, MemoryChunk, MemoryTag, Message, TagRegistry
from app.models.entities import ActionStatus
from app.services.audit.service import AuditService
from app.services.catalog.tag_policy import canonicalize_tag_refs, ensure_user_system_tag, serialize_prompt_tag_catalog
from app.services.memory.service import MemoryService
from app.services.prompts.service import PromptTemplateService
from app.services.providers.registry import ProviderRegistry
from app.services.runtime.prompting import record_prompt_render_artifacts
from app.services.runtime.structured_models import CompactionStructuredOutputModel
from app.services.workspace.targets import ensure_session_state


class CompactionJobService:
    """Executes memory compaction jobs using the configured summary prompt and provider."""

    COMPACTION_COMPRESS_RATIO = 0.8

    def __init__(
        self,
        audit_service: AuditService,
        prompt_service: PromptTemplateService,
        provider_registry: ProviderRegistry,
        memory_service: MemoryService,
    ) -> None:
        self.audit_service = audit_service
        self.prompt_service = prompt_service
        self.provider_registry = provider_registry
        self.memory_service = memory_service

    def execute(self, session: Session, cocoon_id: str, before_message_id: str | None = None) -> None:
        """Compress an earlier portion of the message history into structured long-term memories."""
        cocoon = session.get(Cocoon, cocoon_id)
        if not cocoon:
            raise ValueError("Cocoon not found")
        run = self.audit_service.start_run(session, cocoon_id, None, None, "compaction")
        step = self.audit_service.start_step(session, run, "compaction")
        query = (
            select(Message)
            .where(Message.cocoon_id == cocoon_id)
            .order_by(Message.created_at.asc())
        )
        messages = list(session.scalars(query).all())
        if len(messages) < 2:
            self.audit_service.finish_step(session, step, ActionStatus.completed)
            self.audit_service.finish_run(session, run, ActionStatus.completed)
            return

        selected, retained_start = self._select_messages_for_compaction(
            cocoon,
            messages,
            before_message_id=before_message_id,
        )
        if not selected:
            self.audit_service.finish_step(session, step, ActionStatus.completed)
            self.audit_service.finish_run(session, run, ActionStatus.completed)
            return

        state = ensure_session_state(session, cocoon_id=cocoon_id)
        memory_context = list(
            session.scalars(
                select(MemoryChunk)
                .where(MemoryChunk.cocoon_id == cocoon_id)
                .order_by(MemoryChunk.created_at.desc())
                .limit(5)
            ).all()
        )
        prompt_tag_catalog, prompt_tag_catalog_by_index = serialize_prompt_tag_catalog(
            session,
            target_type="cocoon",
            target_id=cocoon_id,
        )
        all_tags = {
            tag.id: tag
            for tag in session.scalars(
                select(TagRegistry)
                .where(TagRegistry.owner_user_id == cocoon.owner_user_id)
                .order_by(TagRegistry.tag_id.asc())
            ).all()
        }
        variables = {
            "session_state": {
                "relation_score": state.relation_score,
                "persona": state.persona_json,
                "active_tags": [
                    {
                        "tag_id": all_tags[tag_id].tag_id,
                        "brief": all_tags[tag_id].brief,
                    }
                    for tag_id in state.active_tags_json
                    if tag_id in all_tags
                ],
            },
            "tag_catalog": prompt_tag_catalog,
            "visible_messages": [
                {"role": message.role, "content": message.content}
                for message in selected
            ],
            "memory_context": [
                {"scope": memory.scope, "summary": memory.summary, "content": memory.content}
                for memory in memory_context
            ],
        }
        template, revision, snapshot, rendered_prompt = self.prompt_service.render(
            session=session,
            template_type="memory_summary",
            variables=variables,
        )
        record_prompt_render_artifacts(
            session,
            self.audit_service,
            run,
            step,
            template,
            revision,
            snapshot,
            rendered_prompt,
            summary_prefix="memory_summary",
        )
        provider, model, _, runtime_provider_config = self.provider_registry.resolve_chat_provider(
            session,
            cocoon.summary_model_id or cocoon.selected_model_id,
        )
        provider_prompt = self._build_structured_prompt(
            rendered_prompt,
            variables,
        )
        response = provider.generate_structured(
            prompt=provider_prompt,
            messages=[],
            model_name=model.model_name,
            provider_config=runtime_provider_config,
            schema_model=CompactionStructuredOutputModel,
            output_name="cocoon_compaction_output",
        )
        self.audit_service.record_json_artifact(
            session,
            run,
            step,
            "provider_raw_output",
            response.raw_response,
            summary="Provider raw compaction output",
            metadata_json={
                "provider_kind": "chat",
                "model_name": model.model_name,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )
        parsed = CompactionStructuredOutputModel.model_validate(response.parsed or {})
        default_tag_id = ensure_user_system_tag(session, cocoon.owner_user_id).id
        created_chunks: list[MemoryChunk] = []
        for item in parsed.long_term_memories:
            summary = str(item.summary or "").strip()
            content = str(item.content or "").strip()
            if not summary or not content:
                continue
            resolved_tags = [
                payload["id"]
                for index, payload in prompt_tag_catalog_by_index.items()
                if index in set(int(raw) for raw in item.tag_indexes)
            ]
            tag_ids = canonicalize_tag_refs(
                session,
                [default_tag_id, *resolved_tags],
                include_default=True,
                owner_user_id=cocoon.owner_user_id,
            )
            chunk = MemoryChunk(
                cocoon_id=cocoon_id,
                owner_user_id=cocoon.owner_user_id,
                character_id=cocoon.character_id,
                scope=str(item.scope or "summary"),
                content=content,
                summary=summary,
                tags_json=tag_ids,
                meta_json={
                    "compressed_message_ids": [message.id for message in selected],
                    "source_kind": "compaction",
                    "importance": int(item.importance),
                    "compaction_summary": str(parsed.summary or "").strip(),
                },
            )
            session.add(chunk)
            session.flush()
            for tag_id in tag_ids:
                session.add(MemoryTag(memory_chunk_id=chunk.id, tag_id=tag_id))
            self.memory_service.index_memory_chunk(
                session,
                chunk,
                source_text=chunk.summary or chunk.content,
                meta_json=chunk.meta_json,
            )
            created_chunks.append(chunk)
        self.audit_service.record_json_artifact(
            session,
            run,
            step,
            "compaction_result",
            {
                "summary": parsed.summary,
                "memory_chunk_ids": [chunk.id for chunk in created_chunks],
                "compressed_message_ids": [message.id for message in selected],
            },
            summary="Memory compaction summary",
            metadata_json={
                "memory_chunk_count": len(created_chunks),
                "compressed_count": len(selected),
            },
        )
        if created_chunks and retained_start is not None:
            cocoon.context_start_message_id = retained_start.id
        self.audit_service.finish_step(session, step, ActionStatus.completed)
        self.audit_service.finish_run(session, run, ActionStatus.completed)

    def _build_structured_prompt(self, rendered_prompt: str, variables: dict) -> str:
        return (
            "You are producing structured long-term memories for compaction.\n"
            "Only output memories that are worth retrieving in future rounds.\n"
            "Every tag reference must use tag_indexes from the provided numbered tag catalog.\n"
            "Do not invent new tag names or output free-text tags.\n"
            "If nothing durable should be stored, return an empty long_term_memories list.\n"
            "COMPACTION_CONTEXT_JSON_START\n"
            f"{json.dumps(variables, ensure_ascii=False, default=str)}\n"
            "COMPACTION_CONTEXT_JSON_END\n"
            "PROMPT_TEXT_START\n"
            f"{rendered_prompt}\n"
            "PROMPT_TEXT_END"
        )

    def _resolve_anchor_index(
        self,
        messages: list[Message],
        anchor_message_id: str | None,
    ) -> int:
        if not anchor_message_id:
            return 0
        for index, message in enumerate(messages):
            if message.id == anchor_message_id:
                return index
        return 0

    def _resolve_message_index(
        self,
        messages: list[Message],
        message_id: str | None,
    ) -> int | None:
        if not message_id:
            return None
        for index, message in enumerate(messages):
            if message.id == message_id:
                return index
        return None

    def _resolve_default_compaction_selection(
        self,
        cocoon: Cocoon,
        messages: list[Message],
        *,
        start_index: int,
    ) -> tuple[list[Message], Message | None]:
        candidates = messages[start_index:]
        if len(candidates) < 2:
            return [], None
        window = candidates[-int(cocoon.max_context_messages):]
        if len(window) < 2:
            return [], None
        compress_count = min(
            len(window) - 1,
            max(1, math.ceil(int(cocoon.max_context_messages) * self.COMPACTION_COMPRESS_RATIO)),
        )
        if compress_count <= 0 or compress_count >= len(window):
            return [], None
        return window[:compress_count], window[compress_count]

    def _select_messages_for_compaction(
        self,
        cocoon: Cocoon,
        messages: list[Message],
        *,
        before_message_id: str | None,
    ) -> tuple[list[Message], Message | None]:
        start_index = self._resolve_anchor_index(messages, cocoon.context_start_message_id)
        if before_message_id:
            end_index = self._resolve_message_index(messages, before_message_id)
            if end_index is None or end_index <= start_index:
                return [], None
            return messages[start_index:end_index], messages[end_index]
        return self._resolve_default_compaction_selection(
            cocoon,
            messages,
            start_index=start_index,
        )
