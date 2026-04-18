from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ChatDispatchEnvelope:
    stream_id: str
    action_id: str
    cocoon_id: str
    event_type: str
    payload: dict[str, Any]


class ChatDispatchQueue(ABC):
    """Abstract queue used to hand chat actions from API to worker."""

    @abstractmethod
    def enqueue(self, action_id: str, cocoon_id: str, event_type: str, payload: dict[str, Any]) -> int:
        raise NotImplementedError

    @abstractmethod
    def consume_next(self) -> ChatDispatchEnvelope | None:
        raise NotImplementedError

    @abstractmethod
    def ack(self, envelope: ChatDispatchEnvelope) -> None:
        raise NotImplementedError
