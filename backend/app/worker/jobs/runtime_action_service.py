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
        *args,
        event_type: str | None = None,
        payload_json: dict | None = None,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
    ) -> ActionDispatch:
        """Create a running action dispatch for a durable-job-triggered runtime round."""
        if args:
            if len(args) == 2 and event_type is None and payload_json is None:
                event_type = args[0]
                payload_json = args[1]
            elif (
                len(args) == 3
                and cocoon_id is None
                and chat_group_id is None
                and event_type is None
                and payload_json is None
            ):
                cocoon_id = args[0]
                event_type = args[1]
                payload_json = args[2]
            else:
                raise TypeError(
                    "create_runtime_action() accepts either legacy positional args or keyword target args"
                )
        if event_type is None or payload_json is None:
            raise TypeError("create_runtime_action() missing required event_type or payload_json")
        action = ActionDispatch(
            cocoon_id=cocoon_id,
            chat_group_id=chat_group_id,
            event_type=event_type,
            status=ActionStatus.running,
            payload_json=payload_json,
            started_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(action)
        session.flush()
        return action
