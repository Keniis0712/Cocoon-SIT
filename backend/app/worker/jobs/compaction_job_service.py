"""Memory compaction durable job execution service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cocoon, MemoryChunk, Message
from app.models.entities import ActionStatus
from app.services.audit.service import AuditService
from app.services.memory.service import MemoryService
from app.services.prompts.service import PromptTemplateService
from app.services.providers.registry import ProviderRegistry
from app.services.runtime.prompting import record_prompt_render_artifacts


class CompactionJobService:
    """Executes memory compaction jobs using the configured summary prompt and provider."""

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
        """Compress an earlier portion of the message history into a summary memory chunk."""
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

        selected: list[Message] = []
        for message in messages:
            if before_message_id and message.id == before_message_id:
                break
            selected.append(message)
        if not before_message_id:
            selected = messages[: max(1, len(messages) // 2)]
        if not selected:
            selected = messages[:1]

        memory_context = list(
            session.scalars(
                select(MemoryChunk)
                .where(MemoryChunk.cocoon_id == cocoon_id)
                .order_by(MemoryChunk.created_at.desc())
                .limit(5)
            ).all()
        )
        variables = {
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
        response = provider.generate_text(
            prompt=rendered_prompt,
            messages=[],
            model_name=model.model_name,
            provider_config=runtime_provider_config,
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
        summary_text = response.text
        chunk = MemoryChunk(
            cocoon_id=cocoon_id,
            owner_user_id=cocoon.owner_user_id,
            character_id=cocoon.character_id,
            scope="summary",
            content=summary_text,
            summary=summary_text[:200],
            tags_json=[],
            meta_json={"compressed_message_ids": [message.id for message in selected]},
        )
        session.add(chunk)
        session.flush()
        self.memory_service.index_memory_chunk(
            session,
            chunk,
            source_text=chunk.summary or chunk.content,
            meta_json={"compressed_message_ids": [message.id for message in selected]},
        )
        self.audit_service.record_json_artifact(
            session,
            run,
            step,
            "compaction_result",
            {
                "memory_chunk_id": chunk.id,
                "compressed_message_ids": [message.id for message in selected],
            },
            summary="Memory compaction summary",
            metadata_json={
                "memory_chunk_id": chunk.id,
                "compressed_count": len(selected),
            },
        )
        self.audit_service.finish_step(session, step, ActionStatus.completed)
        self.audit_service.finish_run(session, run, ActionStatus.completed)
