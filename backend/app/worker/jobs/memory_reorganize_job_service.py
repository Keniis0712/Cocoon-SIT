"""AI-assisted memory reorganization durable job execution service."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cocoon, MemoryChunk, MemoryTag
from app.models.entities import ActionStatus
from app.services.audit.service import AuditService
from app.services.catalog.tag_policy import canonicalize_tag_refs, ensure_user_system_tag, serialize_prompt_tag_catalog
from app.services.memory.service import MemoryService
from app.services.prompts.service import PromptTemplateService
from app.services.providers.registry import ProviderRegistry
from app.services.runtime.prompting import record_prompt_render_artifacts
from app.services.runtime.structured_models import CompactionStructuredOutputModel


class MemoryReorganizeJobService:
    """Rewrites selected memories into a cleaner set of memories and archives originals."""

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

    def execute(
        self,
        session: Session,
        cocoon_id: str,
        *,
        memory_ids: list[str],
        instructions: str | None = None,
    ) -> None:
        cocoon = session.get(Cocoon, cocoon_id)
        if not cocoon:
            raise ValueError("Cocoon not found")
        memories = list(
            session.scalars(
                select(MemoryChunk).where(
                    MemoryChunk.id.in_(memory_ids),
                    MemoryChunk.status == "active",
                )
            ).all()
        )
        if not memories:
            return
        profile = session.info["container"].system_settings_service.get_memory_profile(
            session,
            cocoon.memory_profile,
        )
        run = self.audit_service.start_run(session, cocoon_id, None, None, "memory_reorganize")
        step = self.audit_service.start_step(session, run, "memory_reorganize")
        prompt_tag_catalog, prompt_tag_catalog_by_index = serialize_prompt_tag_catalog(
            session,
            target_type="cocoon",
            target_id=cocoon_id,
        )
        variables = {
            "instructions": instructions or "Consolidate overlap, keep distinct durable memory, archive redundant fragments.",
            "selected_memories": [
                {
                    "id": memory.id,
                    "memory_pool": memory.memory_pool,
                    "memory_type": memory.memory_type,
                    "summary": memory.summary,
                    "content": memory.content,
                    "tags": list(memory.tags_json or []),
                    "importance": memory.importance,
                    "confidence": memory.confidence,
                }
                for memory in memories
            ],
            "tag_catalog": prompt_tag_catalog,
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
            summary_prefix="memory_reorganize",
        )
        provider, model, _, runtime_provider_config = self.provider_registry.resolve_chat_provider(
            session,
            cocoon.summary_model_id or cocoon.selected_model_id,
        )
        response = provider.generate_structured(
            prompt=self._build_prompt(rendered_prompt, variables),
            messages=[],
            model_name=model.model_name,
            provider_config=runtime_provider_config,
            schema_model=CompactionStructuredOutputModel,
            output_name="memory_reorganize_output",
        )
        parsed = CompactionStructuredOutputModel.model_validate(response.parsed or {})
        self.audit_service.record_json_artifact(
            session,
            run,
            step,
            "provider_raw_output",
            response.raw_response,
            summary="Provider raw memory reorganize output",
            metadata_json={
                "model_name": model.model_name,
                "selected_count": len(memories),
            },
        )
        default_tag_id = ensure_user_system_tag(session, cocoon.owner_user_id).id
        created_ids: list[str] = []
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
            if int(item.importance or 0) < 3:
                candidate = self.memory_service.upsert_candidate(
                    session,
                    cocoon_id=cocoon_id,
                    owner_user_id=cocoon.owner_user_id,
                    character_id=cocoon.character_id,
                    memory_pool=str(item.memory_pool or "tree_private"),
                    memory_type=str(item.memory_type or "summary"),
                    summary=summary,
                    content=content,
                    tags_json=tag_ids,
                    importance=max(0, min(2, int(item.importance or 2))),
                    confidence=max(1, min(5, int(item.confidence or 3))),
                    ttl_hours=int(profile.get("candidate_ttl_hours") or 72),
                    meta_json={"source_kind": "memory_reorganize"},
                )
                if int(candidate.hit_count or 0) >= int(profile.get("candidate_promote_hits") or 2):
                    created_ids.append(
                        self.memory_service.promote_candidate_to_memory(
                            session,
                            candidate,
                            source_kind="memory_reorganize_candidate_promotion",
                        ).id
                    )
                continue
            chunk = MemoryChunk(
                cocoon_id=cocoon_id,
                owner_user_id=cocoon.owner_user_id,
                character_id=cocoon.character_id,
                memory_pool=str(item.memory_pool or "tree_private"),
                memory_type=str(item.memory_type or "summary"),
                scope=str(item.scope or "summary"),
                content=content,
                summary=summary,
                tags_json=tag_ids,
                importance=max(3, min(5, int(item.importance or 3))),
                confidence=max(1, min(5, int(item.confidence or 4))),
                status="active",
                source_kind="memory_reorganize",
                meta_json={
                    "source_kind": "memory_reorganize",
                    "source_memory_ids": [memory.id for memory in memories],
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
            created_ids.append(chunk.id)
        for memory in memories:
            memory.status = "archived"
        self.audit_service.record_json_artifact(
            session,
            run,
            step,
            "compaction_result",
            {
                "source_memory_ids": [memory.id for memory in memories],
                "created_memory_ids": created_ids,
                "summary": parsed.summary,
            },
            summary="Memory reorganize result",
            metadata_json={"created_count": len(created_ids)},
        )
        self.audit_service.finish_step(session, step, ActionStatus.completed)
        self.audit_service.finish_run(session, run, ActionStatus.completed)

    def _build_prompt(self, rendered_prompt: str, variables: dict) -> str:
        return (
            "You are reorganizing a selected set of memories into a cleaner memory set.\n"
            "Merge overlaps, keep important distinctions, and drop noise.\n"
            "Use importance 2 for candidate memory and 3-5 for durable memory.\n"
            "Use only tag_indexes from the provided tag catalog.\n"
            "REORGANIZE_CONTEXT_JSON_START\n"
            f"{json.dumps(variables, ensure_ascii=False, default=str)}\n"
            "REORGANIZE_CONTEXT_JSON_END\n"
            "PROMPT_TEXT_START\n"
            f"{rendered_prompt}\n"
            "PROMPT_TEXT_END"
        )
