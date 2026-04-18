from __future__ import annotations

from collections import deque

from app.services.jobs.chat_dispatch_types import ChatDispatchEnvelope, ChatDispatchQueue


class InMemoryChatDispatchQueue(ChatDispatchQueue):
    """Simple in-process queue used in tests and local development."""

    def __init__(self) -> None:
        self._items: deque[ChatDispatchEnvelope] = deque()
        self._counter = 0

    def enqueue(self, action_id: str, cocoon_id: str, event_type: str, payload: dict) -> int:
        self._counter += 1
        self._items.append(
            ChatDispatchEnvelope(
                stream_id=str(self._counter),
                action_id=action_id,
                cocoon_id=cocoon_id,
                event_type=event_type,
                payload=payload,
            )
        )
        return len(self._items)

    def consume_next(self) -> ChatDispatchEnvelope | None:
        if not self._items:
            return None
        return self._items.popleft()

    def ack(self, envelope: ChatDispatchEnvelope) -> None:
        return
