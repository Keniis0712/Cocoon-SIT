from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import SessionState
from app.services.realtime.hub import RealtimeHub
from app.services.runtime.side_effects import SideEffects
from app.services.runtime.types import ContextPackage, MetaDecision
from app.services.workspace.targets import target_channel_key


class StatePatchService:
    """Applies meta-driven state changes and broadcasts them."""

    def __init__(self, side_effects: SideEffects, realtime_hub: RealtimeHub) -> None:
        self.side_effects = side_effects
        self.realtime_hub = realtime_hub

    def apply_and_publish(
        self,
        session: Session,
        context: ContextPackage,
        meta: MetaDecision,
        *,
        action_id: str,
    ) -> SessionState:
        state = self.side_effects.apply_state_patch(session, context, meta)
        return self.publish_snapshot(
            state,
            action_id=action_id,
            cocoon_id=context.runtime_event.cocoon_id,
            chat_group_id=context.runtime_event.chat_group_id,
        )

    def publish_snapshot(
        self,
        state: SessionState,
        *,
        action_id: str,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
    ) -> SessionState:
        channel_key = target_channel_key(cocoon_id=cocoon_id, chat_group_id=chat_group_id)
        self.realtime_hub.publish(
            channel_key,
            {
                "type": "state_patch",
                "action_id": action_id,
                "cocoon_id": cocoon_id,
                "chat_group_id": chat_group_id,
                "relation_score": state.relation_score,
                "persona_json": state.persona_json,
                "active_tags": state.active_tags_json,
                "current_wakeup_task_id": state.current_wakeup_task_id,
            },
        )
        return state
