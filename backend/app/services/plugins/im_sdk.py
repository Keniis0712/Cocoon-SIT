from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from multiprocessing.queues import Queue
from typing import Any


@dataclass
class ImPluginContext:
    plugin_name: str
    plugin_version: str
    plugin_config: dict[str, Any]
    data_dir: str
    outbound_queue: Queue | None = None

    def heartbeat(self) -> None:
        if not self.outbound_queue:
            return
        self.outbound_queue.put(
            {
                "type": "heartbeat",
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
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )
