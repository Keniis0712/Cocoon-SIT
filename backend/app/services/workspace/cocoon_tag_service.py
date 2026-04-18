"""Workspace cocoon-tag binding service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import CocoonTagBinding, SessionState


class CocoonTagService:
    """Applies cocoon tag bindings and keeps session state tags aligned."""

    def bind_tag(self, session: Session, cocoon_id: str, tag_id: str) -> CocoonTagBinding:
        """Create a cocoon-tag binding and mirror it to the active tag list."""
        binding = CocoonTagBinding(cocoon_id=cocoon_id, tag_id=tag_id)
        session.add(binding)
        state = session.get(SessionState, cocoon_id)
        if state and tag_id not in state.active_tags_json:
            state.active_tags_json = [*state.active_tags_json, tag_id]
        session.flush()
        return binding
