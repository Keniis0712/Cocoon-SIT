from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from multiprocessing.queues import Queue
from queue import Empty
from typing import Any, Awaitable, Callable
from uuid import uuid4


ImRouteHandler = Callable[[Any], "ImInboundRoute | dict[str, Any] | None | Awaitable[ImInboundRoute | dict[str, Any] | None]"]
ImReplyHandler = Callable[[Any], "ImDeliveryResult | dict[str, Any] | bool | None | Awaitable[ImDeliveryResult | dict[str, Any] | bool | None]"]
LifecycleHandler = Callable[[], "None | Awaitable[None]"]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ImInboundRoute:
    target_type: str
    target_id: str
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImPrivateMessage:
    account_id: str
    conversation_id: str
    sender_id: str | None
    sender_display_name: str | None
    text: str
    message_id: str
    occurred_at: str
    sender_user_id: str | None = None
    owner_user_id: str | None = None
    memory_owner_user_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImGroupMessage:
    account_id: str
    conversation_id: str
    sender_id: str | None
    sender_display_name: str | None
    text: str
    message_id: str
    occurred_at: str
    group_name: str | None = None
    sender_user_id: str | None = None
    owner_user_id: str | None = None
    memory_owner_user_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImOutboundReply:
    delivery_id: str
    plugin_id: str
    action_id: str | None
    message_id: str | None
    target_type: str
    target_id: str
    reply_text: str
    source_message_id: str | None
    external_account_id: str | None
    external_conversation_id: str | None
    external_message_id: str | None
    external_sender_id: str | None
    external_sender_display_name: str | None
    metadata_json: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None


@dataclass
class ImDeliveryResult:
    ok: bool
    error: str | None = None
    retryable: bool = True
    metadata_json: dict[str, Any] = field(default_factory=dict)


class ImPluginContext:
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

    async def create_cocoon(
        self,
        *,
        name: str,
        owner_user_id: str | None = None,
        owner_username: str | None = None,
        character_id: str,
        selected_model_id: str,
        parent_id: str | None = None,
        default_temperature: float | None = None,
        max_context_messages: int | None = None,
        auto_compaction_enabled: bool | None = None,
    ) -> dict[str, Any]:
        owner_payload = self._single_identity_payload(
            id_value=owner_user_id,
            username_value=owner_username,
            id_key="owner_user_id",
            username_key="owner_username",
            subject="owner",
        )
        return await self._rpc(
            "create_cocoon",
            {
                "name": name,
                **owner_payload,
                "character_id": character_id,
                "selected_model_id": selected_model_id,
                "parent_id": parent_id,
                "default_temperature": default_temperature,
                "max_context_messages": max_context_messages,
                "auto_compaction_enabled": auto_compaction_enabled,
            },
        )

    async def create_chat_group(
        self,
        *,
        name: str,
        owner_user_id: str | None = None,
        owner_username: str | None = None,
        character_id: str,
        selected_model_id: str,
        initial_member_ids: list[str] | None = None,
        default_temperature: float | None = None,
        max_context_messages: int | None = None,
        auto_compaction_enabled: bool | None = None,
        external_platform: str | None = None,
        external_group_id: str | None = None,
        external_account_id: str | None = None,
    ) -> dict[str, Any]:
        owner_payload = self._single_identity_payload(
            id_value=owner_user_id,
            username_value=owner_username,
            id_key="owner_user_id",
            username_key="owner_username",
            subject="owner",
        )
        return await self._rpc(
            "create_chat_group",
            {
                "name": name,
                **owner_payload,
                "character_id": character_id,
                "selected_model_id": selected_model_id,
                "initial_member_ids": list(initial_member_ids or []),
                "default_temperature": default_temperature,
                "max_context_messages": max_context_messages,
                "auto_compaction_enabled": auto_compaction_enabled,
                "external_platform": external_platform,
                "external_group_id": external_group_id,
                "external_account_id": external_account_id,
            },
        )

    async def verify_user_binding(self, *, username: str, token: str) -> dict[str, Any]:
        return await self._rpc(
            "verify_user_binding",
            {
                "username": username,
                "token": token,
            },
        )

    async def list_accessible_targets(self, *, user_id: str | None = None, username: str | None = None) -> dict[str, Any]:
        identity_payload = self._single_identity_payload(
            id_value=user_id,
            username_value=username,
            id_key="user_id",
            username_key="username",
            subject="user",
        )
        return await self._rpc(
            "list_accessible_targets",
            identity_payload,
        )

    async def list_accessible_characters(self, *, user_id: str | None = None, username: str | None = None) -> dict[str, Any]:
        identity_payload = self._single_identity_payload(
            id_value=user_id,
            username_value=username,
            id_key="user_id",
            username_key="username",
            subject="user",
        )
        return await self._rpc(
            "list_accessible_characters",
            identity_payload,
        )

    async def upsert_im_target_route(
        self,
        *,
        target_type: str,
        target_id: str,
        external_platform: str,
        conversation_kind: str,
        external_account_id: str,
        external_conversation_id: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._rpc(
            "upsert_im_target_route",
            {
                "target_type": target_type,
                "target_id": target_id,
                "external_platform": external_platform,
                "conversation_kind": conversation_kind,
                "external_account_id": external_account_id,
                "external_conversation_id": external_conversation_id,
                "metadata_json": dict(metadata_json or {}),
            },
        )

    async def delete_im_target_route(
        self,
        *,
        external_platform: str,
        conversation_kind: str,
        external_account_id: str,
        external_conversation_id: str,
    ) -> dict[str, Any]:
        return await self._rpc(
            "delete_im_target_route",
            {
                "external_platform": external_platform,
                "conversation_kind": conversation_kind,
                "external_account_id": external_account_id,
                "external_conversation_id": external_conversation_id,
            },
        )

    async def emit_private_message(self, route: ImInboundRoute, message: ImPrivateMessage) -> None:
        self._emit_inbound_message("private", route, message)

    async def emit_group_message(self, route: ImInboundRoute, message: ImGroupMessage) -> None:
        self._emit_inbound_message("group", route, message)

    async def handle_private_message(self, message: ImPrivateMessage) -> ImInboundRoute | None:
        return await self._handle_inbound_message("private", message, self._private_message_handler)

    async def handle_group_message(self, message: ImGroupMessage) -> ImInboundRoute | None:
        return await self._handle_inbound_message("group", message, self._group_message_handler)

    async def run_forever(self, *, poll_interval_seconds: float = 0.2) -> None:
        if self._startup_handler is not None:
            await self._invoke(self._startup_handler)
        last_heartbeat_at = 0.0
        try:
            while True:
                now = asyncio.get_running_loop().time()
                if now - last_heartbeat_at >= self.heartbeat_interval_seconds:
                    self.heartbeat()
                    last_heartbeat_at = now
                message = await self._next_control_message(timeout=poll_interval_seconds, include_rpc_responses=False)
                if not message:
                    continue
                if message.get("type") == "stop":
                    return
                if message.get("type") == "deliver_reply":
                    await self._dispatch_outbound_reply(message)
                    continue
                if message.get("type") == "rpc_response":
                    self._buffered_control_messages.append(message)
        finally:
            if self._shutdown_handler is not None:
                await self._invoke(self._shutdown_handler)

    def _emit(self, payload: dict[str, Any]) -> None:
        if not self.outbound_queue:
            return
        self.outbound_queue.put(payload)

    def _emit_inbound_message(self, message_kind: str, route: ImInboundRoute, message: ImPrivateMessage | ImGroupMessage) -> None:
        self._emit(
            {
                "type": "im_inbound_message",
                "message_kind": message_kind,
                "route": asdict(route),
                "message": asdict(message),
                "occurred_at": _utc_now_iso(),
            }
        )

    async def _handle_inbound_message(
        self,
        message_kind: str,
        message: ImPrivateMessage | ImGroupMessage,
        handler: ImRouteHandler | None,
    ) -> ImInboundRoute | None:
        if handler is None:
            return None
        route_value = await self._invoke(handler, message)
        route = self._coerce_route(route_value)
        if route is None:
            return None
        self._emit_inbound_message(message_kind, route, message)
        return route

    async def _dispatch_outbound_reply(self, envelope: dict[str, Any]) -> None:
        delivery_id = str(envelope.get("delivery_id") or "")
        reply = self._coerce_outbound_reply(envelope.get("reply") or {})
        if self._outbound_reply_handler is None:
            result = ImDeliveryResult(ok=False, error="No outbound reply handler registered", retryable=True)
        else:
            try:
                value = await self._invoke(self._outbound_reply_handler, reply)
            except Exception as exc:  # noqa: BLE001
                result = ImDeliveryResult(ok=False, error=str(exc), retryable=True)
            else:
                result = self._coerce_delivery_result(value)
        self._emit(
            {
                "type": "delivery_result",
                "delivery_id": delivery_id,
                "result": asdict(result),
                "occurred_at": _utc_now_iso(),
            }
        )

    async def _rpc(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = uuid4().hex
        self._emit(
            {
                "type": "rpc_request",
                "request_id": request_id,
                "method": method,
                "payload": payload,
                "occurred_at": _utc_now_iso(),
            }
        )
        while True:
            message = self._pop_buffered_rpc_response(request_id)
            if message is None:
                message = await self._next_queue_message(timeout=0.2)
            if not message:
                continue
            if message.get("type") != "rpc_response":
                self._buffered_control_messages.append(message)
                continue
            if str(message.get("request_id") or "") != request_id:
                self._buffered_control_messages.append(message)
                continue
            if not bool(message.get("ok")):
                raise RuntimeError(str(message.get("error") or f"RPC failed: {method}"))
            payload = message.get("payload") or {}
            if isinstance(payload, dict):
                return payload
            raise RuntimeError(f"RPC returned invalid payload for method {method}")

    async def _next_control_message(self, *, timeout: float, include_rpc_responses: bool = True) -> dict[str, Any] | None:
        buffered = self._pop_buffered_control_message(include_rpc_responses=include_rpc_responses)
        if buffered is not None:
            return buffered
        return await self._next_queue_message(timeout=timeout)

    async def _next_queue_message(self, *, timeout: float) -> dict[str, Any] | None:
        if not self.inbound_queue:
            await asyncio.sleep(timeout)
            return None
        try:
            return await asyncio.to_thread(self.inbound_queue.get, True, timeout)
        except Empty:
            return None

    def _pop_buffered_control_message(self, *, include_rpc_responses: bool) -> dict[str, Any] | None:
        for index, message in enumerate(self._buffered_control_messages):
            if include_rpc_responses or message.get("type") != "rpc_response":
                return self._buffered_control_messages.pop(index)
        return None

    def _pop_buffered_rpc_response(self, request_id: str) -> dict[str, Any] | None:
        for index, message in enumerate(self._buffered_control_messages):
            if message.get("type") == "rpc_response" and str(message.get("request_id") or "") == request_id:
                return self._buffered_control_messages.pop(index)
        return None

    async def _invoke(self, func: Callable[..., Any], *args: Any) -> Any:
        result = func(*args)
        if asyncio.iscoroutine(result):
            return await result
        return result

    def _coerce_route(self, value: Any) -> ImInboundRoute | None:
        if value is None:
            return None
        if isinstance(value, ImInboundRoute):
            return value
        if isinstance(value, dict):
            return ImInboundRoute(
                target_type=str(value.get("target_type") or ""),
                target_id=str(value.get("target_id") or ""),
                metadata_json=dict(value.get("metadata_json") or {}),
            )
        raise TypeError("Inbound route handler must return None, ImInboundRoute, or dict")

    def _coerce_outbound_reply(self, value: dict[str, Any]) -> ImOutboundReply:
        return ImOutboundReply(
            delivery_id=str(value.get("delivery_id") or ""),
            plugin_id=str(value.get("plugin_id") or ""),
            action_id=str(value.get("action_id")) if value.get("action_id") is not None else None,
            message_id=str(value.get("message_id")) if value.get("message_id") is not None else None,
            target_type=str(value.get("target_type") or ""),
            target_id=str(value.get("target_id") or ""),
            reply_text=str(value.get("reply_text") or ""),
            source_message_id=str(value.get("source_message_id")) if value.get("source_message_id") is not None else None,
            external_account_id=str(value.get("external_account_id")) if value.get("external_account_id") is not None else None,
            external_conversation_id=(
                str(value.get("external_conversation_id")) if value.get("external_conversation_id") is not None else None
            ),
            external_message_id=str(value.get("external_message_id")) if value.get("external_message_id") is not None else None,
            external_sender_id=str(value.get("external_sender_id")) if value.get("external_sender_id") is not None else None,
            external_sender_display_name=(
                str(value.get("external_sender_display_name"))
                if value.get("external_sender_display_name") is not None
                else None
            ),
            metadata_json=dict(value.get("metadata_json") or {}),
            created_at=str(value.get("created_at")) if value.get("created_at") is not None else None,
        )

    def _coerce_delivery_result(self, value: Any) -> ImDeliveryResult:
        if value is None:
            return ImDeliveryResult(ok=True)
        if isinstance(value, ImDeliveryResult):
            return value
        if value is True:
            return ImDeliveryResult(ok=True)
        if value is False:
            return ImDeliveryResult(ok=False, error="Outbound reply handler reported failure")
        if isinstance(value, dict):
            return ImDeliveryResult(
                ok=bool(value.get("ok")),
                error=str(value.get("error")) if value.get("error") is not None else None,
                retryable=bool(value.get("retryable", True)),
                metadata_json=dict(value.get("metadata_json") or {}),
            )
        raise TypeError("Outbound reply handler must return None, bool, ImDeliveryResult, or dict")

    def _single_identity_payload(
        self,
        *,
        id_value: str | None,
        username_value: str | None,
        id_key: str,
        username_key: str,
        subject: str,
    ) -> dict[str, str]:
        normalized_id = str(id_value or "").strip()
        normalized_username = str(username_value or "").strip()
        provided = bool(normalized_id) + bool(normalized_username)
        if provided != 1:
            raise ValueError(f"Exactly one of {id_key} or {username_key} is required for {subject}")
        if normalized_id:
            return {id_key: normalized_id}
        return {username_key: normalized_username}
