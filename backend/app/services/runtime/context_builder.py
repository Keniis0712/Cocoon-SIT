"""Runtime context builder composed from smaller context subservices."""

from sqlalchemy.orm import Session

from app.models import Character, Cocoon, SessionState
from app.services.memory.service import MemoryService
from app.services.runtime.context.external_context_service import ExternalContextService
from app.services.runtime.context.message_window_service import MessageWindowService
from app.services.runtime.types import ContextPackage, RuntimeEvent


class ContextBuilder:
    """Assembles the full runtime context package for a single action."""

    def __init__(
        self,
        memory_service: MemoryService,
        message_window_service: MessageWindowService | None = None,
        external_context_service: ExternalContextService | None = None,
    ):
        self.memory_service = memory_service
        self.message_window_service = message_window_service or MessageWindowService()
        self.external_context_service = external_context_service or ExternalContextService(
            memory_service=memory_service,
            message_window_service=self.message_window_service,
        )

    def build(self, session: Session, event: RuntimeEvent) -> ContextPackage:
        cocoon = session.get(Cocoon, event.cocoon_id)
        if not cocoon:
            raise ValueError(f"Cocoon not found: {event.cocoon_id}")
        character = session.get(Character, cocoon.character_id)
        if not character:
            raise ValueError(f"Character not found: {cocoon.character_id}")
        state = session.get(SessionState, event.cocoon_id)
        if not state:
            state = SessionState(cocoon_id=event.cocoon_id)
            session.add(state)
            session.flush()

        visible_messages = self.message_window_service.list_visible_messages(
            session,
            event.cocoon_id,
            cocoon.max_context_messages,
            state.active_tags_json,
        )
        query_text = self._resolve_query_text(event, visible_messages)
        memory_hits = self.memory_service.retrieve_visible_memories(
            session=session,
            cocoon_id=event.cocoon_id,
            active_tags=state.active_tags_json,
            query_text=query_text,
            limit=5,
        )
        external_context = self.external_context_service.build(session, event)
        return ContextPackage(
            runtime_event=event,
            cocoon=cocoon,
            character=character,
            session_state=state,
            visible_messages=visible_messages,
            memory_context=[hit.memory for hit in memory_hits],
            memory_hits=memory_hits,
            external_context=external_context,
        )

    def _resolve_query_text(self, event: RuntimeEvent, visible_messages: list) -> str | None:
        if event.event_type == "chat":
            for message in reversed(visible_messages):
                if message.role == "user":
                    return message.content
        if event.event_type in {"pull", "merge"}:
            source_cocoon_id = event.payload.get("source_cocoon_id")
            if source_cocoon_id:
                return f"{event.event_type}:{source_cocoon_id}"
        if event.event_type == "wakeup":
            return str(event.payload.get("reason") or "scheduled wakeup")
        return None
