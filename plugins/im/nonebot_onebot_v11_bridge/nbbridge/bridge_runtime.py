from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from queue import Empty
from typing import Any

from app.services.plugins.im_sdk import (
    ImDeliveryResult,
    ImGroupMessage,
    ImInboundRoute,
    ImOutboundReply,
    ImPrivateMessage,
)


class BridgeRuntimeMixin:
    def run(self) -> None:
        asyncio.run(self._sync_attached_routes())
        self.ctx.on_outbound_reply(self._handle_outbound_reply)
        control_thread = threading.Thread(
            target=self._run_control_loop_thread,
            name="nonebot-onebot-v11-control",
            daemon=True,
        )
        control_thread.start()
        try:
            self._run_nonebot_thread()
        finally:
            self.stop_event.set()
            control_thread.join(timeout=2)

    def _run_control_loop_thread(self) -> None:
        try:
            asyncio.run(self.ctx.run_forever())
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_runtime_error(f"IM control loop failed: {exc}")
            self.stop_event.set()

    async def _dispatch_inbound_event(self, payload: dict[str, Any]) -> None:
        kind = str(payload.get("message_kind") or "").strip()
        route = self._binding_route(payload)
        if route is None:
            return
        identity = self._inbound_identity(payload)
        if kind == "private":
            message = ImPrivateMessage(
                account_id=str(payload["account_id"]),
                conversation_id=str(payload["conversation_id"]),
                sender_id=str(payload.get("sender_id"))
                if payload.get("sender_id") is not None
                else None,
                sender_display_name=(
                    str(payload.get("sender_display_name"))
                    if payload.get("sender_display_name") is not None
                    else None
                ),
                text=str(payload["text"]),
                message_id=str(payload["message_id"]),
                occurred_at=str(payload["occurred_at"]),
                sender_user_id=identity["sender_user_id"],
                owner_user_id=identity["owner_user_id"],
                memory_owner_user_id=identity["memory_owner_user_id"],
                raw_payload=dict(payload.get("raw_payload") or {}),
                metadata_json=dict(payload.get("metadata_json") or {}),
            )
            await self.ctx.emit_private_message(route, message)
            return
        if kind == "group":
            message = ImGroupMessage(
                account_id=str(payload["account_id"]),
                conversation_id=str(payload["conversation_id"]),
                sender_id=str(payload.get("sender_id"))
                if payload.get("sender_id") is not None
                else None,
                sender_display_name=(
                    str(payload.get("sender_display_name"))
                    if payload.get("sender_display_name") is not None
                    else None
                ),
                text=str(payload["text"]),
                message_id=str(payload["message_id"]),
                occurred_at=str(payload["occurred_at"]),
                group_name=str(payload.get("group_name"))
                if payload.get("group_name") is not None
                else None,
                sender_user_id=identity["sender_user_id"],
                owner_user_id=identity["owner_user_id"],
                memory_owner_user_id=identity["memory_owner_user_id"],
                raw_payload=dict(payload.get("raw_payload") or {}),
                metadata_json=dict(payload.get("metadata_json") or {}),
            )
            await self.ctx.emit_group_message(route, message)

    async def _handle_outbound_reply(self, reply: ImOutboundReply) -> ImDeliveryResult:
        future: Future[ImDeliveryResult] = Future()
        self.outbound_replies.put((reply, future))
        try:
            return await asyncio.wait_for(asyncio.wrap_future(future), timeout=20)
        except asyncio.TimeoutError:
            return ImDeliveryResult(
                ok=False, error="Timed out waiting for NoneBot delivery", retryable=True
            )

    def _binding_route(self, payload: dict[str, Any]) -> ImInboundRoute | None:
        message_kind = str(payload.get("message_kind") or "").strip()
        account_id = str(payload.get("account_id") or "")
        conversation_id = str(payload.get("conversation_id") or "")
        if message_kind == "group":
            group_state = self.route_store.get_group_state(account_id, conversation_id)
            if (
                not group_state
                or not bool(group_state.get("enabled"))
                or not bool(group_state.get("attached"))
            ):
                return None
            route = dict(group_state.get("route") or {})
        else:
            binding = self.route_store.get_binding(
                message_kind,
                account_id,
                conversation_id,
            )
            if not binding or not bool(binding.get("attached")):
                return None
            route = dict(binding.get("route") or {})
            if route:
                metadata_json = dict(route.get("metadata_json") or {})
                metadata_json["tags"] = list(binding.get("tags") or [])
                route["metadata_json"] = metadata_json
        if not route:
            return None
        return ImInboundRoute(
            target_type=str(route.get("target_type") or ""),
            target_id=str(route.get("target_id") or ""),
            metadata_json=dict(route.get("metadata_json") or {}),
        )

    def _platform_binding(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if str(payload.get("message_kind") or "") != "private":
            return None
        return self.route_store.get_platform_binding(
            str(payload.get("account_id") or ""),
            str(payload.get("conversation_id") or ""),
        )

    def _resolve_owner_identity(self, payload: dict[str, Any]) -> dict[str, str]:
        binding = self._platform_binding(payload)
        if binding and binding.get("platform_user_id"):
            return {"owner_user_id": str(binding["platform_user_id"])}
        return {
            "owner_username": str(
                self.config.get("default_owner_username") or ""
            ).strip()
        }

    def _owner_lookup_identity(self, payload: dict[str, Any]) -> dict[str, str]:
        owner_identity = self._resolve_owner_identity(payload)
        if "owner_user_id" in owner_identity:
            return {"user_id": str(owner_identity["owner_user_id"])}
        return {"username": str(owner_identity.get("owner_username") or "")}

    def _inbound_identity(self, payload: dict[str, Any]) -> dict[str, str | None]:
        binding = self._platform_binding(payload)
        platform_user_id = ""
        if binding is not None:
            platform_user_id = str(binding.get("platform_user_id") or "").strip()
        if not platform_user_id:
            return {
                "sender_user_id": None,
                "owner_user_id": None,
                "memory_owner_user_id": None,
            }
        return {
            "sender_user_id": platform_user_id,
            "owner_user_id": platform_user_id,
            "memory_owner_user_id": platform_user_id,
        }

    def _remember_bot(self, bot: Any) -> None:
        bot_id = str(getattr(bot, "self_id", "") or "")
        if not bot_id:
            return
        with self._bot_lock:
            self._connected_bots[bot_id] = bot

    def _select_bot(self, account_id: str | None) -> Any | None:
        with self._bot_lock:
            if account_id and account_id in self._connected_bots:
                return self._connected_bots[account_id]
            if not self._connected_bots:
                return None
            return next(iter(self._connected_bots.values()))

    def _run_nonebot_thread(self) -> None:
        try:
            self._apply_nonebot_env()
            import nonebot
            from nonebot import on_message
            from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
            from nonebot.adapters.onebot.v11 import (
                GroupMessageEvent,
                PrivateMessageEvent,
            )

            nonebot.init()
            driver = nonebot.get_driver()
            driver.register_adapter(OneBotV11Adapter)
            sender_loop_started = False

            async def ensure_sender_loop() -> None:
                nonlocal sender_loop_started
                if sender_loop_started:
                    return
                sender_loop_started = True
                asyncio.create_task(self._nonebot_sender_loop())

            listener = on_message(priority=self.config["message_priority"], block=False)

            @listener.handle()
            async def _handle_message(bot, event) -> None:
                await ensure_sender_loop()
                self._remember_bot(bot)
                payload = self._normalize_onebot_event(
                    bot, event, PrivateMessageEvent, GroupMessageEvent
                )
                if payload is None:
                    return
                if (
                    str(payload.get("message_kind") or "") == "private"
                    and self._is_command(str(payload.get("text") or ""))
                ):
                    response = await self._handle_command(payload)
                    if response:
                        await self._send_direct_message(
                            bot, event, response, PrivateMessageEvent, GroupMessageEvent
                        )
                    return
                route = self._binding_route(payload)
                if route is None:
                    return
                await self._dispatch_inbound_event(payload)

            nonebot.run()
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_runtime_error(f"NoneBot runtime failed: {exc}")
            self.stop_event.set()
            raise

    async def _nonebot_sender_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                reply, future = await asyncio.to_thread(
                    self.outbound_replies.get, True, 0.2
                )
            except Empty:
                continue
            if future.done():
                continue
            bot = self._select_bot(reply.external_account_id)
            if bot is None:
                future.set_result(
                    ImDeliveryResult(
                        ok=False,
                        error="No active OneBot bot connection",
                        retryable=True,
                    )
                )
                continue
            try:
                await self._send_onebot_reply(bot, reply)
            except Exception as exc:  # noqa: BLE001
                future.set_result(
                    ImDeliveryResult(ok=False, error=str(exc), retryable=True)
                )
                continue
            future.set_result(ImDeliveryResult(ok=True))

    async def _send_onebot_reply(self, bot: Any, reply: ImOutboundReply) -> None:
        conversation_kind = str(
            reply.metadata_json.get("conversation_kind") or ""
        ).strip()
        if conversation_kind == "group":
            group_id = int(str(reply.external_conversation_id or "").strip())
            await bot.send_group_msg(group_id=group_id, message=reply.reply_text)
            return
        user_target = str(
            reply.external_conversation_id or reply.external_sender_id or ""
        ).strip()
        if not user_target:
            raise RuntimeError("Missing OneBot private target user_id")
        await bot.send_private_msg(user_id=int(user_target), message=reply.reply_text)

    async def _send_direct_message(
        self,
        bot: Any,
        event: Any,
        message: str,
        private_event_type: Any,
        group_event_type: Any,
    ) -> None:
        if isinstance(event, group_event_type):
            await bot.send_group_msg(group_id=int(event.group_id), message=message)
            return
        if isinstance(event, private_event_type):
            await bot.send_private_msg(user_id=int(event.user_id), message=message)
            return
        await bot.send(event=event, message=message)
