"""Workspace cocoon-tag binding service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CocoonTagBinding, SessionState


class CocoonTagService:
    """Applies cocoon tag bindings and keeps session state tags aligned."""

    def bind_tag(self, session: Session, cocoon_id: str, tag_id: str) -> CocoonTagBinding:
        """Create a cocoon-tag binding and mirror it to the active tag list."""
        existing = session.scalar(
            select(CocoonTagBinding).where(
                CocoonTagBinding.cocoon_id == cocoon_id,
                CocoonTagBinding.tag_id == tag_id,
            )
        )
        if existing:
            return existing
        binding = CocoonTagBinding(cocoon_id=cocoon_id, tag_id=tag_id)
        session.add(binding)
        state = session.get(SessionState, cocoon_id)
        if state and tag_id not in state.active_tags_json:
            state.active_tags_json = [*state.active_tags_json, tag_id]
        session.flush()
        return binding

    def unbind_tag(self, session: Session, cocoon_id: str, tag_id: str) -> CocoonTagBinding:
        """Remove a cocoon-tag binding and mirror it to the active tag list."""
        binding = session.scalar(
            select(CocoonTagBinding).where(
                CocoonTagBinding.cocoon_id == cocoon_id,
                CocoonTagBinding.tag_id == tag_id,
            )
        )
        if not binding:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag binding not found")
        state = session.get(SessionState, cocoon_id)
        if state:
            state.active_tags_json = [item for item in state.active_tags_json if item != tag_id]
        session.delete(binding)
        session.flush()
        return binding
