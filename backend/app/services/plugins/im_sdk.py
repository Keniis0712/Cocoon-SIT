from __future__ import annotations

from multiprocessing.queues import Queue
from typing import Any

from app.services.plugins.im_sdk_models import (
    ImDeliveryResult,
    ImGroupMessage,
    ImInboundRoute,
    ImOutboundReply,
    ImPrivateMessage,
    ImReplyHandler,
    ImRouteHandler,
    LifecycleHandler,
)
from app.services.plugins.im_sdk_models import (
    utc_now_iso as _utc_now_iso,
)
from app.services.plugins.im_sdk_rpc import ImPluginRpcMixin
from app.services.plugins.im_sdk_runtime import ImPluginRuntimeMixin


class ImPluginContext(ImPluginRpcMixin, ImPluginRuntimeMixin):
    def __init__(
        self,
        *,
        plugin_name: str,
        plugin_version: str,
        plugin_config: dict[str, Any],
        data_dir: str,
        inbound_queue: Queue | None = None,
        outbound_queue: Queue | None = None,
        heartbeat_interval_seconds: float = 2.0,
    ) -> None:
        self.plugin_name = plugin_name
        self.plugin_version = plugin_version
        self.plugin_config = plugin_config
        self.data_dir = data_dir
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self._startup_handler: LifecycleHandler | None = None
        self._shutdown_handler: LifecycleHandler | None = None
        self._private_message_handler: ImRouteHandler | None = None
        self._group_message_handler: ImRouteHandler | None = None
        self._outbound_reply_handler: ImReplyHandler | None = None
        self._buffered_control_messages: list[dict[str, Any]] = []

    def on_startup(self, handler: LifecycleHandler) -> LifecycleHandler:
        self._startup_handler = handler
        return handler

    def on_shutdown(self, handler: LifecycleHandler) -> LifecycleHandler:
        self._shutdown_handler = handler
        return handler

    def on_private_message(self, handler: ImRouteHandler) -> ImRouteHandler:
        self._private_message_handler = handler
        return handler

    def on_group_message(self, handler: ImRouteHandler) -> ImRouteHandler:
        self._group_message_handler = handler
        return handler

    def on_outbound_reply(self, handler: ImReplyHandler) -> ImReplyHandler:
        self._outbound_reply_handler = handler
        return handler

    def heartbeat(self) -> None:
        self._emit(
            {
                "type": "heartbeat",
                "occurred_at": _utc_now_iso(),
            }
        )

    def report_runtime_error(self, message: str) -> None:
        self._emit(
            {
                "type": "error",
                "error": message,
                "occurred_at": _utc_now_iso(),
            }
        )

    def report_user_error(self, user_id: str, message: str) -> None:
        self._emit(
            {
                "type": "user_error",
                "user_id": user_id,
                "error": message,
                "occurred_at": _utc_now_iso(),
            }
        )

    def clear_user_error(self, user_id: str) -> None:
        self._emit(
            {
                "type": "user_error_clear",
                "user_id": user_id,
                "occurred_at": _utc_now_iso(),
            }
        )

    async def emit_private_message(self, route: ImInboundRoute, message: ImPrivateMessage) -> None:
        self._emit_inbound_message("private", route, message)

    async def emit_group_message(self, route: ImInboundRoute, message: ImGroupMessage) -> None:
        self._emit_inbound_message("group", route, message)

    async def handle_private_message(self, message: ImPrivateMessage) -> ImInboundRoute | None:
        return await self._handle_inbound_message("private", message, self._private_message_handler)

    async def handle_group_message(self, message: ImGroupMessage) -> ImInboundRoute | None:
        return await self._handle_inbound_message("group", message, self._group_message_handler)


__all__ = [
    "ImDeliveryResult",
    "ImGroupMessage",
    "ImInboundRoute",
    "ImOutboundReply",
    "ImPluginContext",
    "ImPrivateMessage",
]
