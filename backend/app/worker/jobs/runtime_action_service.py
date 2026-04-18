"""Helpers for creating runtime actions from durable jobs."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import ActionDispatch
from app.models.entities import ActionStatus


class RuntimeActionService:
    """Creates action records used to route durable jobs through ChatRuntime."""

    def create_runtime_action(
        self,
        session: Session,
        cocoon_id: str,
        event_type: str,
        payload_json: dict,
    ) -> ActionDispatch:
        """Create a running action dispatch for a durable-job-triggered runtime round."""
        action = ActionDispatch(
            cocoon_id=cocoon_id,
            event_type=event_type,
            status=ActionStatus.running,
            payload_json=payload_json,
            started_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(action)
        session.flush()
        return action
