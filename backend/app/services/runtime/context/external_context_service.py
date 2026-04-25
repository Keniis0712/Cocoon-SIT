"""External-context subservice for pull, merge, and wakeup rounds."""

from __future__ import annotations

from sqlalchemy.orm import Session

from sqlalchemy import select

from app.models import Cocoon, CocoonTagBinding, SessionState, TagRegistry
from app.services.memory.service import MemoryService
from app.services.catalog.tag_policy import get_tag_by_any_ref
from app.services.runtime.context.message_window_service import MessageWindowService
from app.services.runtime.types import RuntimeEvent
from app.services.workspace.targets import get_session_state


class ExternalContextService:
    """Builds event-specific runtime context that comes from outside the active cocoon."""

    def __init__(
        self,
        memory_service: MemoryService,
        message_window_service: MessageWindowService,
    ) -> None:
        self.memory_service = memory_service
        self.message_window_service = message_window_service

    def build(self, session: Session, event: RuntimeEvent) -> dict:
        """Return extra context needed for special runtime events."""
        external_context: dict = {}
        if event.event_type == "wakeup":
            external_context["wakeup_context"] = event.payload
            return external_context

        if event.event_type not in {"pull", "merge"}:
            return external_context

        source_cocoon_id = event.payload.get("source_cocoon_id")
        if not source_cocoon_id:
            return external_context

        source_cocoon = session.get(Cocoon, source_cocoon_id)
        if not source_cocoon:
            return external_context

        source_state = get_session_state(session, cocoon_id=source_cocoon_id)
        source_active_tags = source_state.active_tags_json if source_state else []
        source_messages = self.message_window_service.list_visible_messages(
            session,
            source_cocoon.max_context_messages,
            source_active_tags,
            cocoon_id=source_cocoon_id,
        )
        source_memories = self.memory_service.get_visible_memories(
            session=session,
            cocoon_id=source_cocoon_id,
            active_tags=source_active_tags,
            query_text=str(event.payload.get("source_cocoon_id") or source_cocoon_id),
            limit=5,
        )
        visible_target_tags = set()
        for item in session.scalars(
            select(CocoonTagBinding).where(CocoonTagBinding.cocoon_id == event.cocoon_id)
        ).all():
            tag = get_tag_by_any_ref(session, item.tag_id)
            visible_target_tags.add(tag.id if tag else item.tag_id)

        def _is_visible(items_tags: list[str] | None) -> bool:
            normalized = [
                tag.id if tag else str(tag_ref)
                for tag_ref in (items_tags or [])
                for tag in [get_tag_by_any_ref(session, tag_ref)]
            ]
            if not normalized:
                return True
            return set(normalized).issubset(visible_target_tags)

        source_messages = [
            message
            for message in source_messages
            if _is_visible(message.tags_json)
        ]
        source_memories = [
            memory
            for memory in source_memories
            if _is_visible(memory.tags_json)
        ]
        external_context.update(
            {
                "source_cocoon": source_cocoon,
                "source_state": source_state,
                "source_messages": source_messages,
                "source_memories": source_memories,
            }
        )
        if event.event_type == "merge":
            external_context["merge_context"] = {
                "source_cocoon": {
                    "id": source_cocoon.id,
                    "name": source_cocoon.name,
                },
                "source_state": {
                    "relation_score": source_state.relation_score if source_state else 0,
                    "persona_json": source_state.persona_json if source_state else {},
                    "active_tags_json": source_state.active_tags_json if source_state else [],
                },
                "source_messages": [
                    {"role": message.role, "content": message.content}
                    for message in source_messages
                ],
                "source_memories": [
                    {"scope": memory.scope, "summary": memory.summary, "content": memory.content}
                    for memory in source_memories
                ],
            }
        return external_context
