"""Realtime backplane abstractions for websocket event fan-out."""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from redis import Redis


EventHandler = Callable[[str, dict[str, Any]], None]


class RealtimeBackplane(ABC):
    """Abstract transport used to broadcast events beyond the local process."""

    @abstractmethod
    def publish(self, cocoon_id: str, event: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, handler: EventHandler) -> None:
        raise NotImplementedError

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError


class InMemoryRealtimeBackplane(RealtimeBackplane):
    """In-process backplane used in tests and single-instance development."""

    def __init__(self) -> None:
        self.handlers: list[EventHandler] = []

    def publish(self, cocoon_id: str, event: dict[str, Any]) -> None:
        for handler in list(self.handlers):
            handler(cocoon_id, event)

    def subscribe(self, handler: EventHandler) -> None:
        self.handlers.append(handler)

    def start(self) -> None:
        return

    def stop(self) -> None:
        return


class RedisRealtimeBackplane(RealtimeBackplane):
    """Redis Pub/Sub backplane used for shared realtime delivery."""

    def __init__(self, redis_url: str, channel_prefix: str):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.channel_prefix = channel_prefix
        self.handlers: list[EventHandler] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def channel_name(self) -> str:
        return f"{self.channel_prefix}:*"

    def publish(self, cocoon_id: str, event: dict[str, Any]) -> None:
        channel = f"{self.channel_prefix}:{cocoon_id}"
        payload = json.dumps({"cocoon_id": cocoon_id, "event": event}, ensure_ascii=False)
        self.redis.publish(channel, payload)

    def subscribe(self, handler: EventHandler) -> None:
        self.handlers.append(handler)

    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self) -> None:
        pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        pubsub.psubscribe(self.channel_name())
        while not self._stop_event.is_set():
            message = pubsub.get_message(timeout=1.0)
            if not message or message.get("type") != "pmessage":
                continue
            data = json.loads(message["data"])
            cocoon_id = data["cocoon_id"]
            event = data["event"]
            for handler in list(self.handlers):
                handler(cocoon_id, event)
        pubsub.close()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
