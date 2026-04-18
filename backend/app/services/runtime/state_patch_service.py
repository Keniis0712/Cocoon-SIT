from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import SessionState
from app.services.realtime.hub import RealtimeHub
from app.services.runtime.side_effects import SideEffects
from app.services.runtime.types import ContextPackage, MetaDecision


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
        return self.publish_snapshot(context.cocoon.id, state, action_id=action_id)

    def publish_snapshot(self, cocoon_id: str, state: SessionState, *, action_id: str) -> SessionState:
        self.realtime_hub.publish(
            cocoon_id,
            {
                "type": "state_patch",
                "action_id": action_id,
                "relation_score": state.relation_score,
                "persona_json": state.persona_json,
                "active_tags": state.active_tags_json,
                "current_wakeup_task_id": state.current_wakeup_task_id,
            },
        )
        return state
