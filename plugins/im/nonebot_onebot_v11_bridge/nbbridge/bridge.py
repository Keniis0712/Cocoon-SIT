from __future__ import annotations

import threading
from concurrent.futures import Future
from pathlib import Path
from queue import Queue
from typing import Any

from app.services.plugins.im_sdk import (
    ImDeliveryResult,
    ImOutboundReply,
    ImPluginContext,
)

from .bridge_commands import BridgeCommandMixin
from .bridge_payload import BridgePayloadMixin
from .bridge_runtime import BridgeRuntimeMixin
from .bridge_targets import BridgeTargetMixin
from .config import normalize_config, validate_settings
from .store import RouteStore


class NoneBotOneBotBridge(
    BridgeRuntimeMixin, BridgePayloadMixin, BridgeCommandMixin, BridgeTargetMixin
):
    LIST_PAGE_SIZE = 10

    def __init__(self, ctx: ImPluginContext) -> None:
        self.ctx = ctx
        self.config = normalize_config(ctx.plugin_config)
        self.route_store = RouteStore(Path(ctx.data_dir) / "routes.json")
        self.stop_event = threading.Event()
        self.outbound_replies: Queue[
            tuple[ImOutboundReply, Future[ImDeliveryResult]]
        ] = Queue()
        self._bot_lock = threading.Lock()
        self._connected_bots: dict[str, Any] = {}


def run(ctx: ImPluginContext) -> None:
    bridge = NoneBotOneBotBridge(ctx)
    bridge.run()


__all__ = ["NoneBotOneBotBridge", "run", "validate_settings"]
