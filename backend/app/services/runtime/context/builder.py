"""Runtime context builder composed from smaller context subservices."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Character, ChatGroupRoom, Cocoon, TagRegistry, User
from app.services.catalog.system_settings_service import SystemSettingsService
from app.services.catalog.tag_policy import (
    is_tag_visible_in_target,
    resolve_tag_owner_user_id_for_target,
    serialize_prompt_tag_catalog,
)
from app.services.memory.service import MemoryService
from app.services.runtime.context.external_context_service import ExternalContextService
from app.services.runtime.context.message_window_service import MessageWindowService
from app.services.runtime.types import ContextPackage, RuntimeEvent
from app.services.runtime.scheduling.wakeup_tasks import list_pending_wakeup_tasks
from app.services.workspace.targets import ensure_session_state, get_target_task_state


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
        conversation = self._resolve_conversation(session, event)
        character = session.get(Character, conversation.character_id)
        if not character:
            raise ValueError(f"Character not found: {conversation.character_id}")
        state = ensure_session_state(
            session,
            cocoon_id=event.cocoon_id,
            chat_group_id=event.chat_group_id,
        )
        task_state = get_target_task_state(
            session,
            cocoon_id=event.cocoon_id,
            chat_group_id=event.chat_group_id,
        )
        profile = self._resolve_memory_profile(session, conversation)

        visible_messages = self.message_window_service.list_visible_messages(
            session,
            conversation.max_context_messages,
            state.active_tags_json,
            cocoon_id=event.cocoon_id,
            chat_group_id=event.chat_group_id,
            context_start_message_id=getattr(conversation, "context_start_message_id", None),
        )
        memory_owner_user_id = self._resolve_memory_owner_user_id(event, conversation, visible_messages)
        query_text = self._resolve_query_text(event, visible_messages)
        memory_lookup = self._memory_lookup_scope(
            event,
            owner_user_id=memory_owner_user_id,
            character_id=character.id,
        )
        fact_cache_entries = (
            getattr(self.memory_service, "list_fact_cache_entries", lambda *args, **kwargs: [])(
                session,
                cocoon_id=event.cocoon_id,
                chat_group_id=event.chat_group_id,
                limit=5,
            )
            if profile.get("read_fact_cache", True)
            else []
        )
        memory_hits = self.memory_service.retrieve_visible_memories(
            session=session,
            active_tags=state.active_tags_json,
            cocoon_id=event.cocoon_id,
            chat_group_id=event.chat_group_id,
            owner_user_id=memory_lookup["owner_user_id"],
            character_id=memory_lookup["character_id"],
            query_text=query_text,
            limit=5,
            profile=profile,
        )
        external_context = self.external_context_service.build(session, event)
        external_context["fact_cache_entries"] = [
            {
                "id": item.id,
                "cache_key": item.cache_key,
                "summary": item.summary,
                "content": item.content,
                "valid_until": item.valid_until.isoformat() if item.valid_until else None,
                "meta_json": item.meta_json,
            }
            for item in fact_cache_entries
        ]
        if task_state:
            external_context["task_state"] = {
                "task_name": task_state.task_name,
                "goal": task_state.goal,
                "progress": task_state.progress,
                "status": task_state.status,
                "meta_json": task_state.meta_json,
                "expires_at": task_state.expires_at.isoformat() if task_state.expires_at else None,
                "completed_at": task_state.completed_at.isoformat() if task_state.completed_at else None,
            }
        if runtime_timezone := self._resolve_runtime_timezone_fallback(
            session,
            conversation=conversation,
            memory_owner_user_id=memory_owner_user_id,
        ):
            external_context["runtime_timezone_fallback"] = runtime_timezone
        pending_wakeups = list_pending_wakeup_tasks(
            session,
            cocoon_id=event.cocoon_id,
            chat_group_id=event.chat_group_id,
        )
        external_context["pending_wakeups"] = [
            {
                "id": task.id,
                "run_at": task.run_at.isoformat(),
                "reason": task.reason,
                "status": task.status,
                "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
                "superseded_by_task_id": task.superseded_by_task_id,
                "payload_json": task.payload_json,
            }
            for task in pending_wakeups
        ]
        owner_user_id = resolve_tag_owner_user_id_for_target(
            session,
            cocoon_id=event.cocoon_id,
            chat_group_id=event.chat_group_id,
        )
        tags = (
            list(
                session.scalars(
                    select(TagRegistry).where(TagRegistry.owner_user_id == owner_user_id)
                ).all()
            )
            if owner_user_id
            else []
        )
        prompt_tag_catalog, prompt_tag_catalog_by_index = serialize_prompt_tag_catalog(
            session,
            target_type=event.target_type,
            target_id=event.target_id,
        )
        external_context["tag_catalog_by_ref"] = {
            **{
                tag.id: {
                    "id": tag.id,
                    "tag_id": tag.tag_id,
                    "brief": tag.brief,
                    "visibility": tag.visibility,
                    "is_isolated": tag.is_isolated,
                    "is_system": tag.is_system,
                    "visible_in_target": is_tag_visible_in_target(
                        session,
                        tag,
                        target_type=event.target_type,
                        target_id=event.target_id,
                    ),
                    "meta_json": tag.meta_json,
                }
                for tag in tags
            },
            **{
                tag.tag_id: {
                    "id": tag.id,
                    "tag_id": tag.tag_id,
                    "brief": tag.brief,
                    "visibility": tag.visibility,
                    "is_isolated": tag.is_isolated,
                    "is_system": tag.is_system,
                    "visible_in_target": is_tag_visible_in_target(
                        session,
                        tag,
                        target_type=event.target_type,
                        target_id=event.target_id,
                    ),
                    "meta_json": tag.meta_json,
                }
                for tag in tags
            },
        }
        external_context["prompt_tag_catalog"] = prompt_tag_catalog
        external_context["prompt_tag_catalog_by_index"] = prompt_tag_catalog_by_index
        return ContextPackage(
            runtime_event=event,
            conversation=conversation,
            character=character,
            session_state=state,
            task_state=task_state,
            visible_messages=visible_messages,
            memory_context=[hit.memory for hit in memory_hits],
            fact_cache_entries=fact_cache_entries,
            memory_profile=profile,
            memory_owner_user_id=memory_owner_user_id,
            memory_hits=memory_hits,
            external_context=external_context,
        )

    def _resolve_conversation(self, session: Session, event: RuntimeEvent) -> Cocoon | ChatGroupRoom:
        if event.chat_group_id:
            room = session.get(ChatGroupRoom, event.chat_group_id)
            if not room:
                raise ValueError(f"Chat group room not found: {event.chat_group_id}")
            return room
        cocoon = session.get(Cocoon, event.cocoon_id)
        if not cocoon:
            raise ValueError(f"Cocoon not found: {event.cocoon_id}")
        return cocoon

    def _resolve_memory_owner_user_id(
        self,
        event: RuntimeEvent,
        conversation: Cocoon | ChatGroupRoom,
        visible_messages: list,
    ) -> str | None:
        if sender_user_id := event.payload.get("memory_owner_user_id"):
            return str(sender_user_id)
        if sender_user_id := event.payload.get("sender_user_id"):
            return str(sender_user_id)
        if event.target_type == "cocoon":
            return conversation.owner_user_id
        if event.payload.get("external_sender_id") or event.payload.get("external_sender_display_name"):
            return conversation.owner_user_id
        for message in reversed(visible_messages):
            if message.role == "user" and message.sender_user_id:
                return message.sender_user_id
        return conversation.owner_user_id

    def _resolve_query_text(self, event: RuntimeEvent, visible_messages: list) -> str | None:
        if event.event_type == "chat":
            for message in reversed(visible_messages):
                if message.role == "user" and not message.is_retracted:
                    return message.content
        if event.event_type in {"pull", "merge"}:
            source_cocoon_id = event.payload.get("source_cocoon_id")
            if source_cocoon_id:
                return f"{event.event_type}:{source_cocoon_id}"
        if event.event_type == "wakeup":
            return str(event.payload.get("reason") or "scheduled wakeup")
        return None

    def _resolve_memory_profile(self, session: Session, conversation: Cocoon | ChatGroupRoom) -> dict:
        container = session.info.get("container")
        if container and getattr(container, "system_settings_service", None):
            return container.system_settings_service.get_memory_profile(
                session,
                getattr(conversation, "memory_profile", None),
            )
        profile_name = str(getattr(conversation, "memory_profile", None) or "meta_reply")
        default_profile = SystemSettingsService.DEFAULT_MEMORY_PROFILES.get(
            profile_name,
            SystemSettingsService.DEFAULT_MEMORY_PROFILES["meta_reply"],
        )
        return dict(default_profile) | {"name": profile_name}

    def _memory_lookup_scope(
        self,
        event: RuntimeEvent,
        *,
        owner_user_id: str | None,
        character_id: str,
    ) -> dict[str, str | None]:
        if event.target_type == "cocoon":
            return {"owner_user_id": None, "character_id": None}
        return {"owner_user_id": owner_user_id, "character_id": character_id}

    def _resolve_runtime_timezone_fallback(
        self,
        session: Session,
        *,
        conversation: Cocoon | ChatGroupRoom,
        memory_owner_user_id: str | None,
    ) -> str | None:
        candidate_user_ids: list[str] = []
        for raw_value in (memory_owner_user_id, conversation.owner_user_id):
            if raw_value is None:
                continue
            user_id = str(raw_value).strip()
            if user_id and user_id not in candidate_user_ids:
                candidate_user_ids.append(user_id)
        for user_id in candidate_user_ids:
            timezone = session.scalar(select(User.timezone).where(User.id == user_id))
            if isinstance(timezone, str) and timezone.strip():
                return timezone.strip()
        return None
