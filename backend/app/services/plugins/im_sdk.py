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
