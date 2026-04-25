from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from multiprocessing.queues import Queue
from typing import Any


@dataclass
class ExternalEventContext:
    plugin_name: str
    plugin_version: str
    event_name: str
    plugin_config: dict[str, Any]
    event_config: dict[str, Any]
    data_dir: str
    user_config: dict[str, Any] | None = None
    user_id: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    outbound_queue: Queue | None = None

    def emit_event(self, envelope: dict[str, Any]) -> None:
        if not self.outbound_queue:
            return
        self.outbound_queue.put(
            {
                "type": "external_event",
                "plugin_event": self.event_name,
                "envelope": envelope,
            }
        )

    def heartbeat(self) -> None:
        if not self.outbound_queue:
            return
        self.outbound_queue.put(
            {
                "type": "heartbeat",
                "plugin_event": self.event_name,
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )

    def report_user_error(self, user_id: str, message: str) -> None:
        if not self.outbound_queue:
            return
        self.outbound_queue.put(
            {
                "type": "user_error",
                "user_id": user_id,
                "error": message,
                "plugin_event": self.event_name,
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )

    def clear_user_error(self, user_id: str) -> None:
        if not self.outbound_queue:
            return
        self.outbound_queue.put(
            {
                "type": "user_error_clear",
                "user_id": user_id,
                "plugin_event": self.event_name,
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )
