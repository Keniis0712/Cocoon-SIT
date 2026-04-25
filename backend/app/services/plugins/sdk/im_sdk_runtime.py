from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict
from queue import Empty
from typing import Any
from uuid import uuid4

from app.services.plugins.sdk.im_sdk_models import (
    ImDeliveryResult,
    ImGroupMessage,
    ImInboundRoute,
    ImOutboundReply,
    ImPrivateMessage,
    ImRouteHandler,
    utc_now_iso,
)


class ImPluginRuntimeMixin:
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
                message = await self._next_control_message(
                    timeout=poll_interval_seconds, include_rpc_responses=False
                )
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

    def _emit_inbound_message(
        self, message_kind: str, route: ImInboundRoute, message: ImPrivateMessage | ImGroupMessage
    ) -> None:
        self._emit(
            {
                "type": "im_inbound_message",
                "message_kind": message_kind,
                "route": asdict(route),
                "message": asdict(message),
                "occurred_at": utc_now_iso(),
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
            result = ImDeliveryResult(
                ok=False, error="No outbound reply handler registered", retryable=True
            )
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
                "occurred_at": utc_now_iso(),
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
                "occurred_at": utc_now_iso(),
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

    async def _next_control_message(
        self, *, timeout: float, include_rpc_responses: bool = True
    ) -> dict[str, Any] | None:
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

    def _pop_buffered_control_message(
        self, *, include_rpc_responses: bool
    ) -> dict[str, Any] | None:
        for index, message in enumerate(self._buffered_control_messages):
            if include_rpc_responses or message.get("type") != "rpc_response":
                return self._buffered_control_messages.pop(index)
        return None

    def _pop_buffered_rpc_response(self, request_id: str) -> dict[str, Any] | None:
        for index, message in enumerate(self._buffered_control_messages):
            if (
                message.get("type") == "rpc_response"
                and str(message.get("request_id") or "") == request_id
            ):
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
            message_id=str(value.get("message_id"))
            if value.get("message_id") is not None
            else None,
            target_type=str(value.get("target_type") or ""),
            target_id=str(value.get("target_id") or ""),
            reply_text=str(value.get("reply_text") or ""),
            source_message_id=str(value.get("source_message_id"))
            if value.get("source_message_id") is not None
            else None,
            external_account_id=str(value.get("external_account_id"))
            if value.get("external_account_id") is not None
            else None,
            external_conversation_id=(
                str(value.get("external_conversation_id"))
                if value.get("external_conversation_id") is not None
                else None
            ),
            external_message_id=str(value.get("external_message_id"))
            if value.get("external_message_id") is not None
            else None,
            external_sender_id=str(value.get("external_sender_id"))
            if value.get("external_sender_id") is not None
            else None,
            external_sender_display_name=(
                str(value.get("external_sender_display_name"))
                if value.get("external_sender_display_name") is not None
                else None
            ),
            metadata_json=dict(value.get("metadata_json") or {}),
            created_at=str(value.get("created_at"))
            if value.get("created_at") is not None
            else None,
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
